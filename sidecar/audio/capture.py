"""System audio capture via the Swift ScreenCaptureKit helper.

Spawns the audio-helper binary as a subprocess and reads raw 16-bit
signed LE PCM at 48kHz mono from its stdout, then resamples to 16kHz
using proper decimation. This captures the REMOTE party's audio.
"""

import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
from scipy.signal import decimate  # type: ignore[import-untyped]

# Swift helper outputs at 48kHz, we resample to 16kHz in Python
INPUT_SAMPLE_RATE = 48000
OUTPUT_SAMPLE_RATE = 16000
DECIMATION_FACTOR = INPUT_SAMPLE_RATE // OUTPUT_SAMPLE_RATE  # 3
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

# Read in chunks that produce 30ms at 16kHz after decimation
OUTPUT_CHUNK_SAMPLES = int(OUTPUT_SAMPLE_RATE * 30 / 1000)  # 480
INPUT_CHUNK_SAMPLES = OUTPUT_CHUNK_SAMPLES * DECIMATION_FACTOR  # 1440
CHUNK_BYTES = INPUT_CHUNK_SAMPLES * SAMPLE_WIDTH

# Locate the audio helper relative to this file
_AUDIO_HELPER_DIR = Path(__file__).parent.parent.parent / "audio-helper"
_DEFAULT_HELPER_PATH = _AUDIO_HELPER_DIR / "AudioCapture"


class SystemAudioCapture:
    """Captures system audio via the Swift ScreenCaptureKit helper."""

    def __init__(
        self,
        on_audio_chunk: Callable[[np.ndarray], None],
        helper_dir: Path | str = _AUDIO_HELPER_DIR,
        app_bundle_id: str | None = None,
    ):
        self.on_audio_chunk = on_audio_chunk
        self.helper_dir = Path(helper_dir)
        self.app_bundle_id = app_bundle_id
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return

        swift_source = self.helper_dir / "Sources" / "AudioCapture" / "main.swift"
        compiled_binary = self.helper_dir / "AudioCapture"

        # On macOS 26+, compiled binaries need their own Screen Recording
        # permission grant. The `swift` interpreter typically already has it,
        # so we prefer running the source directly during development.
        # For production (bundled .app), the compiled binary will be signed
        # with proper entitlements.
        if swift_source.exists():
            cmd = ["swift", str(swift_source)]
        elif compiled_binary.exists():
            cmd = [str(compiled_binary)]
        else:
            raise FileNotFoundError(
                f"Audio helper not found in {self.helper_dir}. "
                "Run ./scripts/build-audio-helper.sh first."
            )

        if self.app_bundle_id:
            cmd.extend(["--app", self.app_bundle_id])

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        # Start a thread to read and print stderr from the helper
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _read_stderr(self) -> None:
        """Read and print stderr from the Swift helper for diagnostics."""
        assert self._process is not None
        assert self._process.stderr is not None
        for line in self._process.stderr:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            print(f"[audio-helper] {line.rstrip()}", flush=True)

    def _read_loop(self) -> None:
        """Read raw PCM from the helper's stdout in fixed-size chunks."""
        assert self._process is not None
        assert self._process.stdout is not None

        buffer = b""
        while self._running:
            data = self._process.stdout.read(CHUNK_BYTES - len(buffer))
            if not data:
                break  # Process exited or pipe closed
            buffer += data

            while len(buffer) >= CHUNK_BYTES:
                chunk_bytes = buffer[:CHUNK_BYTES]
                buffer = buffer[CHUNK_BYTES:]

                # Convert bytes to float32 [-1, 1]
                samples_48k = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                # Resample 48kHz -> 16kHz with proper anti-aliasing filter
                samples_16k = decimate(samples_48k, DECIMATION_FACTOR, zero_phase=True).astype(np.float32)
                self.on_audio_chunk(samples_16k)

    @staticmethod
    def list_apps(helper_dir: Path | str = _AUDIO_HELPER_DIR) -> list[dict[str, str]]:
        """List available apps for audio capture."""
        helper_dir = Path(helper_dir)
        swift_source = helper_dir / "Sources" / "AudioCapture" / "main.swift"
        compiled_binary = helper_dir / "AudioCapture"

        if swift_source.exists():
            cmd = ["swift", str(swift_source), "--list"]
        elif compiled_binary.exists():
            cmd = [str(compiled_binary), "--list"]
        else:
            return []

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        apps = []
        for line in result.stderr.strip().split("\n"):
            if " — " in line:
                bundle_id, name = line.split(" — ", 1)
                apps.append({"bundle_id": bundle_id.strip(), "name": name.strip()})
        return apps
