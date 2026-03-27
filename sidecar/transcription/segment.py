"""Transcript segment dataclass."""

from dataclasses import dataclass, field
import uuid


@dataclass
class TranscriptSegment:
    """A single transcribed segment of speech."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str = ""
    speaker: str = "UNKNOWN"  # "REMOTE" or "LOCAL"
    timestamp: float = 0.0  # seconds since meeting start
    duration: float = 0.0  # seconds
    is_final: bool = True
