"""Quick verification script for the audio pipeline.

Captures both REMOTE (system audio) and LOCAL (microphone) streams
for a few seconds and saves them to WAV files for manual inspection.

Usage:
    cd sidecar && uv run python ../tests/test_audio_capture.py
"""

import struct
import sys
import time
from pathlib import Path

import numpy as np

# Add sidecar to path
sys.path.insert(0, str(Path(__file__).parent.parent / "sidecar"))

from audio.capture import SystemAudioCapture
from audio.microphone import MicrophoneCapture

SAMPLE_RATE = 16000
DURATION_S = 10

remote_chunks: list[np.ndarray] = []
local_chunks: list[np.ndarray] = []


def on_remote_chunk(chunk: np.ndarray) -> None:
    remote_chunks.append(chunk)


def on_local_chunk(chunk: np.ndarray) -> None:
    local_chunks.append(chunk)


def write_wav(filename: str, audio: np.ndarray) -> None:
    """Write float32 audio [-1, 1] to a 16-bit WAV file."""
    int16_audio = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    num_samples = len(int16_audio)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample

    with open(filename, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))  # PCM format
        f.write(struct.pack("<H", 1))  # mono
        f.write(struct.pack("<I", SAMPLE_RATE))
        f.write(struct.pack("<I", SAMPLE_RATE * 2))  # byte rate
        f.write(struct.pack("<H", 2))  # block align
        f.write(struct.pack("<H", 16))  # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(int16_audio.tobytes())


def main() -> None:
    output_dir = Path(__file__).parent.parent / "models"

    print(f"Recording {DURATION_S} seconds of audio...")
    print("  REMOTE: system audio (play something in another app)")
    print("  LOCAL:  microphone")
    print()

    # List available devices
    print("Available microphones:")
    for dev in MicrophoneCapture.list_devices():
        print(f"  [{dev['index']}] {dev['name']}")
    print()

    remote = SystemAudioCapture(on_audio_chunk=on_remote_chunk)
    local = MicrophoneCapture(on_audio_chunk=on_local_chunk)

    try:
        remote.start()
        local.start()
        print("Recording...")

        for i in range(DURATION_S):
            time.sleep(1)
            r_chunks = len(remote_chunks)
            l_chunks = len(local_chunks)
            print(f"  {i+1}s — REMOTE chunks: {r_chunks}, LOCAL chunks: {l_chunks}")

    finally:
        remote.stop()
        local.stop()

    # Save WAV files
    if remote_chunks:
        remote_audio = np.concatenate(remote_chunks)
        remote_path = output_dir / "test_remote.wav"
        write_wav(str(remote_path), remote_audio)
        print(f"\nREMOTE audio saved: {remote_path} ({len(remote_audio)/SAMPLE_RATE:.1f}s)")
    else:
        print("\nNo REMOTE audio captured (is Screen Recording permission granted?)")

    if local_chunks:
        local_audio = np.concatenate(local_chunks)
        local_path = output_dir / "test_local.wav"
        write_wav(str(local_path), local_audio)
        print(f"LOCAL audio saved:  {local_path} ({len(local_audio)/SAMPLE_RATE:.1f}s)")
    else:
        print("No LOCAL audio captured (is a microphone available?)")


if __name__ == "__main__":
    main()
