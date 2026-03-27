"""Voice Activity Detection using Silero VAD.

Uses a timer-based approach: accumulates audio in fixed windows (5 seconds),
checks if the window contains speech using Silero VAD, and emits the full
window for transcription if it does. This ensures Whisper always gets enough
context for accurate transcription.
"""

import numpy as np
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

SAMPLE_RATE = 16000

_cached_model = None


def get_vad_model():
    """Get or load the cached Silero VAD model (singleton)."""
    global _cached_model
    if _cached_model is None:
        _cached_model = load_silero_vad(onnx=True)
    return _cached_model


class VADSegmenter:
    """Accumulates audio in fixed windows and emits windows containing speech.

    Instead of trying to find exact speech boundaries (which produces
    segments too short for Whisper), this uses fixed-size windows and
    checks each window for speech. Whisper gets full windows with enough
    context for accurate transcription.
    """

    def __init__(
        self,
        window_duration_s: float = 10.0,
        speech_threshold: float = 0.05,
        min_speech_ratio: float = 0.03,
        model=None,
    ):
        """
        Args:
            window_duration_s: Size of each audio window sent to Whisper.
            speech_threshold: Silero VAD threshold for speech detection.
            min_speech_ratio: Minimum fraction of window that must be speech
                to emit it (0.1 = at least 10% speech).
        """
        self.window_samples = int(SAMPLE_RATE * window_duration_s)
        self.speech_threshold = speech_threshold
        self.min_speech_ratio = min_speech_ratio
        self._model = model or get_vad_model()
        self._buffer: list[np.ndarray] = []
        self._buffer_samples = 0

    def reset(self) -> None:
        self._model.reset_states()
        self._buffer.clear()
        self._buffer_samples = 0

    def process_chunk(self, chunk: np.ndarray) -> list[np.ndarray]:
        """Process a 30ms audio chunk. Returns speech windows when ready."""
        self._buffer.append(chunk)
        self._buffer_samples += len(chunk)

        if self._buffer_samples < self.window_samples:
            return []

        # Window is full — check for speech and emit if found
        window = np.concatenate(self._buffer)
        self._buffer.clear()
        self._buffer_samples = 0

        if self._contains_speech(window):
            return [window]
        return []

    def flush(self) -> list[np.ndarray]:
        """Flush remaining audio at end of meeting."""
        if not self._buffer or self._buffer_samples < SAMPLE_RATE:
            self._buffer.clear()
            self._buffer_samples = 0
            return []

        window = np.concatenate(self._buffer)
        self._buffer.clear()
        self._buffer_samples = 0

        if self._contains_speech(window):
            return [window]
        return []

    def _contains_speech(self, audio: np.ndarray) -> bool:
        """Check if an audio window contains enough speech to transcribe."""
        self._model.reset_states()
        tensor = torch.from_numpy(audio.astype(np.float32))
        timestamps = get_speech_timestamps(
            tensor,
            self._model,
            sampling_rate=SAMPLE_RATE,
            threshold=self.speech_threshold,
            min_speech_duration_ms=250,
        )

        if not timestamps:
            return False

        # Calculate total speech duration
        speech_samples = sum(ts["end"] - ts["start"] for ts in timestamps)
        speech_ratio = speech_samples / len(audio)
        return speech_ratio >= self.min_speech_ratio
