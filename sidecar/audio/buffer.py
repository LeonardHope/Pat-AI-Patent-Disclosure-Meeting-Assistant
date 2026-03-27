"""Audio buffer that accumulates chunks and provides them to downstream consumers.

Each audio stream (REMOTE and LOCAL) has its own buffer. Chunks are accumulated
and can be retrieved as larger segments for transcription.
"""

import threading
import time
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 16000


@dataclass
class AudioSegment:
    """A segment of audio with metadata."""
    audio: np.ndarray  # float32, [-1, 1]
    speaker: str  # "REMOTE" or "LOCAL"
    timestamp: float  # seconds since meeting start
    duration: float  # seconds


class AudioBuffer:
    """Thread-safe audio buffer that accumulates chunks into segments."""

    def __init__(self, speaker: str, max_duration_s: float = 30.0):
        self.speaker = speaker
        self.max_duration_s = max_duration_s
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._start_time: float | None = None
        self._meeting_start: float | None = None

    def set_meeting_start(self, t: float) -> None:
        self._meeting_start = t

    def add_chunk(self, chunk: np.ndarray) -> None:
        """Add a 30ms audio chunk to the buffer."""
        with self._lock:
            if self._start_time is None:
                self._start_time = time.monotonic()
            self._chunks.append(chunk)

    def get_and_clear(self) -> AudioSegment | None:
        """Get accumulated audio as a segment and clear the buffer."""
        with self._lock:
            if not self._chunks:
                return None

            audio = np.concatenate(self._chunks)
            duration = len(audio) / SAMPLE_RATE
            timestamp = 0.0
            if self._meeting_start is not None and self._start_time is not None:
                timestamp = self._start_time - self._meeting_start

            self._chunks.clear()
            self._start_time = None

            return AudioSegment(
                audio=audio,
                speaker=self.speaker,
                timestamp=timestamp,
                duration=duration,
            )

    @property
    def duration_s(self) -> float:
        """Current buffered audio duration in seconds."""
        with self._lock:
            total_samples = sum(len(c) for c in self._chunks)
            return total_samples / SAMPLE_RATE

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._chunks) == 0
