"""Whisper transcription engine using pywhispercpp.

Provides on-device speech-to-text using whisper.cpp with Metal
acceleration on Apple Silicon. Processes audio segments from the
VAD and returns TranscriptSegment objects.
"""

import threading
from pathlib import Path

import numpy as np
from pywhispercpp.model import Model

from .segment import TranscriptSegment

_MODELS_DIR = Path(__file__).parent.parent.parent / "models"

# Comprehensive Whisper hallucination filter
# Sources: sachaarbonel/whisper-hallucinations dataset, OpenAI discussions,
# arxiv.org/html/2501.11378v1, reddit.com/r/LocalLLaMA/comments/1rlqfd7
_HALLUCINATIONS = {
    # YouTube-trained artifacts
    "thank you", "thank you for watching", "thanks for watching",
    "thank you for watching please subscribe", "thanks for watching please subscribe",
    "please subscribe", "subscribe to my channel", "like and subscribe",
    "like this video", "comment below", "thanks for listening",
    "thank you for listening", "thank you very much", "thanks",
    "thank you so much", "thanks so much",
    # Closing remarks
    "bye", "bye bye", "goodbye", "see you", "see you next time",
    "i love you", "the end", "that's all", "that's it",
    "i'll see you in the next video", "i'll see you next time",
    # Subtitle artifacts
    "subtitles by the amara org community", "subtitles by the amara.org community",
    "satsang with mooji", "transcript emily beynon",
    "amara.org", "mooji",
    # Noise artifacts
    "you", "oh", "ah", "hmm", "um", "uh", "so", "the",
    ".", "-", "...", "okay", "right",
    # Foreign language leaks on silence
    "sous-titrage société radio-canada",
    "sous-titres réalisés par la communauté d'amara.org",
    "sottotitoli creati dalla comunità amara.org",
    "untertitel von stephanie geiges",
}

# Patterns that indicate hallucination (partial matches)
_HALLUCINATION_PATTERNS = [
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "like and subscribe",
    "subtitles by",
    "amara.org",
    "subscribe to",
    "see you in the next",
    "see you next time",
    "for more information visit",
    "www.",
    "http",
]


class WhisperEngine:
    """On-device Whisper transcription via whisper.cpp."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        n_threads: int = 4,
    ):
        if model_path is None:
            # Prefer large-v3 (better accuracy) over turbo (faster)
            full = _MODELS_DIR / "ggml-large-v3.bin"
            turbo = _MODELS_DIR / "ggml-large-v3-turbo.bin"
            model_path = full if full.exists() else turbo
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Whisper model not found at {self.model_path}. "
                "Run ./scripts/download-whisper-model.sh"
            )

        self._model = Model(
            str(self.model_path),
            n_threads=n_threads,
            params_sampling_strategy=1,  # beam search (more accurate)
            print_progress=False,
            print_realtime=False,
            print_timestamps=False,
        )
        self._model._params.beam_search = {"beam_size": 5, "patience": 1.0}
        self._model._params.no_context = True  # Disable context carry — causes looping
        self._vocab_prompt = ""
        self._lock = threading.Lock()
        self._recent_texts: list[str] = []  # Track recent outputs to skip duplicates

    def set_vocab_prompt(self, prompt: str) -> None:
        """Set domain vocabulary to improve transcription accuracy."""
        self._vocab_prompt = prompt
        if prompt:
            self._model._params.initial_prompt = prompt
        # Metal GPU cannot handle concurrent command encoders
        self._lock = threading.Lock()

    def transcribe(
        self,
        audio: np.ndarray,
        speaker: str = "UNKNOWN",
        timestamp: float = 0.0,
    ) -> TranscriptSegment | None:
        """Transcribe an audio segment.

        Args:
            audio: float32 numpy array [-1, 1] at 16kHz mono.
            speaker: Speaker label ("REMOTE" or "LOCAL").
            timestamp: Seconds since meeting start.

        Returns:
            TranscriptSegment with transcribed text, or None if no speech detected.
        """
        if len(audio) < 8000:  # < 0.5 seconds — too short
            return None

        audio = audio.astype(np.float32)

        with self._lock:
            segments = self._model.transcribe(audio)

        # Combine all segment texts
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        if not text or text.isspace() or len(text.strip()) < 3:
            return None

        # Filter underscore/dash-only output
        if all(c in "_-–—. \t\n" for c in text):
            return None

        # Filter hallucinations — exact match
        cleaned = text.strip().lower().rstrip(".!,?")
        if cleaned in _HALLUCINATIONS:
            return None

        # Filter hallucinations — pattern match
        for pattern in _HALLUCINATION_PATTERNS:
            if pattern in cleaned:
                return None

        # Filter repetitive output (Whisper looping bug)
        words = text.split()
        if len(words) >= 4:
            from collections import Counter
            # Single-word repetition: "the the the the"
            counts = Counter(w.lower().strip(".,!?") for w in words)
            most_common_count = counts.most_common(1)[0][1]
            if most_common_count > len(words) * 0.5:
                return None

            # Phrase-level looping: "but I think the export but I think the export"
            text_lower = text.lower()
            for phrase_len in range(3, min(15, len(words) // 2 + 1)):
                phrase = " ".join(words[:phrase_len]).lower().strip(".,!?")
                if len(phrase) < 8:
                    continue
                count = text_lower.count(phrase)
                if count >= 3:
                    # This phrase appears 3+ times — it's a loop
                    # Return just the first occurrence
                    text = " ".join(words[:phrase_len])
                    break

        # Skip if identical or very similar to recent outputs
        text_normalized = text.strip().lower()
        for recent in self._recent_texts:
            if text_normalized == recent:
                return None
            # Check if >80% overlap (catches slight variations of same stuck output)
            if len(text_normalized) > 20 and len(recent) > 20:
                shorter = min(len(text_normalized), len(recent))
                common = sum(a == b for a, b in zip(text_normalized, recent))
                if common / shorter > 0.8:
                    return None

        # Keep last 5 outputs for dedup
        self._recent_texts.append(text_normalized)
        if len(self._recent_texts) > 5:
            self._recent_texts.pop(0)

        duration = len(audio) / 16000.0

        return TranscriptSegment(
            text=text,
            speaker=speaker,
            timestamp=timestamp,
            duration=duration,
            is_final=True,
        )
