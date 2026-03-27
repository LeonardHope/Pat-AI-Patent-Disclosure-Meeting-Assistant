"""End-to-end test: audio capture -> VAD -> Whisper -> labeled transcript.

Captures both REMOTE (system audio) and LOCAL (microphone) streams,
runs VAD to detect speech segments, transcribes with Whisper, and
prints labeled output to the terminal.

Usage:
    cd sidecar && uv run python ../tests/test_transcription_pipeline.py
"""

import sys
import time
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "sidecar"))

from audio.capture import SystemAudioCapture
from audio.microphone import MicrophoneCapture
from audio.vad import VADSegmenter
from transcription.engine import WhisperEngine

DURATION_S = 30


def main() -> None:
    print("=" * 60)
    print("Transcription Pipeline Test")
    print(f"Duration: {DURATION_S}s")
    print("Play audio in another app for REMOTE transcription")
    print("Speak into the mic for LOCAL transcription")
    print("=" * 60)
    print()

    # Initialize components
    print("Loading Whisper model...")
    t0 = time.time()
    whisper = WhisperEngine()
    print(f"Whisper loaded in {time.time() - t0:.1f}s")

    print("Loading VAD...")
    remote_segmenter = VADSegmenter()
    local_segmenter = VADSegmenter()
    print("VAD ready")
    print()

    meeting_start = time.monotonic()
    segment_count = 0
    lock = threading.Lock()

    def transcribe_segment(audio: np.ndarray, speaker: str) -> None:
        nonlocal segment_count
        timestamp = time.monotonic() - meeting_start
        seg = whisper.transcribe(audio, speaker=speaker, timestamp=timestamp)
        if seg and seg.text.strip():
            with lock:
                segment_count += 1
                elapsed = time.monotonic() - meeting_start
                mins = int(elapsed) // 60
                secs = int(elapsed) % 60
                duration = len(audio) / 16000
                print(f"  [{mins:02d}:{secs:02d}] [{seg.speaker:6s}] ({duration:.1f}s) {seg.text}")

    def on_remote_chunk(chunk: np.ndarray) -> None:
        segments = remote_segmenter.process_chunk(chunk)
        for segment in segments:
            threading.Thread(
                target=transcribe_segment, args=(segment, "REMOTE"), daemon=True
            ).start()

    def on_local_chunk(chunk: np.ndarray) -> None:
        segments = local_segmenter.process_chunk(chunk)
        for segment in segments:
            threading.Thread(
                target=transcribe_segment, args=(segment, "LOCAL"), daemon=True
            ).start()

    # Start capture
    remote = SystemAudioCapture(on_audio_chunk=on_remote_chunk)
    local = MicrophoneCapture(on_audio_chunk=on_local_chunk)

    print(f"Starting capture for {DURATION_S}s...")
    print("-" * 60)
    remote.start()
    local.start()

    try:
        time.sleep(DURATION_S)
    except KeyboardInterrupt:
        print("\nStopped by user")

    remote.stop()
    local.stop()

    # Flush remaining audio
    for segmenter, speaker in [(remote_segmenter, "REMOTE"), (local_segmenter, "LOCAL")]:
        for segment in segmenter.flush():
            transcribe_segment(segment, speaker)

    # Wait for in-flight transcriptions
    time.sleep(3)

    print("-" * 60)
    print(f"Total segments transcribed: {segment_count}")
    print("Pipeline test complete.")


if __name__ == "__main__":
    main()
