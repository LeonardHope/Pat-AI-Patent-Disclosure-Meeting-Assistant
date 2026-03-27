"""Microphone audio capture via sounddevice.

Captures the LOCAL party's audio (the patent attorney) from the system
microphone. Outputs float32 numpy arrays normalized to [-1, 1] in 30ms chunks.
"""

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)


class MicrophoneCapture:
    """Captures audio from the system microphone."""

    def __init__(
        self,
        on_audio_chunk: Callable[[np.ndarray], None],
        device: int | str | None = None,
    ):
        self.on_audio_chunk = on_audio_chunk
        self.device = device
        self._stream: sd.InputStream | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_SAMPLES,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if not self._running:
            return
        # indata is (frames, channels) — flatten to 1D
        chunk = indata[:, 0].copy()
        self.on_audio_chunk(chunk)

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        inputs = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                inputs.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                })
        return inputs
