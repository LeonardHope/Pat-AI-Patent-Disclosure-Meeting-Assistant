"""In-memory meeting session state.

Tracks the ephemeral transcript, uploaded documents, and suggestions
for the current meeting. Everything is discarded when the meeting ends
(after optional summary generation).
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from transcription.segment import TranscriptSegment


class MeetingState(str, Enum):
    IDLE = "idle"
    PRE_CALL = "pre_call"
    ACTIVE = "active"
    ENDED = "ended"


@dataclass
class Suggestion:
    id: str
    category: str
    priority: str  # HIGH, MEDIUM, LOW
    suggestion: str
    context: str
    timestamp: float = 0.0


@dataclass
class MeetingSession:
    """In-memory state for the current meeting."""
    state: MeetingState = MeetingState.IDLE
    start_time: float = 0.0
    transcript: list[TranscriptSegment] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    document_texts: list[str] = field(default_factory=list)
    document_names: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.state = MeetingState.ACTIVE
        self.start_time = time.monotonic()
        self.transcript.clear()
        self.suggestions.clear()

    def end(self) -> None:
        self.state = MeetingState.ENDED

    def discard(self) -> None:
        """Discard all ephemeral data after summary generation."""
        self.transcript.clear()
        self.suggestions.clear()
        self.document_texts.clear()
        self.document_names.clear()
        self.state = MeetingState.IDLE

    def add_segment(self, segment: TranscriptSegment) -> None:
        self.transcript.append(segment)

    def get_transcript_text(self, last_n_seconds: float | None = None) -> str:
        """Get transcript as text, optionally limited to last N seconds."""
        segments = self.transcript
        if last_n_seconds is not None and segments:
            cutoff = segments[-1].timestamp - last_n_seconds
            segments = [s for s in segments if s.timestamp >= cutoff]
        return "\n".join(
            f"[{s.speaker}] {s.text}" for s in segments if s.text.strip()
        )

    def update_suggestions(self, new_suggestions: list[Suggestion]) -> None:
        """Replace suggestions with a fresh ranked set."""
        self.suggestions = new_suggestions[:5]  # enforce max
