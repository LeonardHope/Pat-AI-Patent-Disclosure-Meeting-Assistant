"""Builds the LLM prompt context from transcript, documents, and current suggestions.

Keeps the context compact to minimize LLM inference time (~20s per call).
"""

from ai.prompts.system_prompt import SYSTEM_PROMPT
from meeting.session import MeetingSession, Suggestion


def build_suggestion_prompt(
    session: MeetingSession,
    max_suggestions: int = 5,
    transcript_window_s: float = 180.0,  # last 3 minutes (keep it short for speed)
    max_doc_chars: int = 1500,
) -> list[dict[str, str]]:
    """Build the messages list for the LLM suggestion call."""
    system = SYSTEM_PROMPT.format(max_suggestions=max_suggestions)

    parts = []

    # Pre-meeting documents (brief summary only)
    if session.document_texts:
        parts.append("## Disclosure Documents (summary)")
        for name, text in zip(session.document_names, session.document_texts):
            truncated = text[:max_doc_chars]
            if len(text) > max_doc_chars:
                truncated += "..."
            parts.append(f"### {name}\n{truncated}")
        parts.append("")

    # Rolling transcript — only recent conversation
    transcript = session.get_transcript_text(last_n_seconds=transcript_window_s)
    if transcript:
        parts.append("## Recent Transcript")
        parts.append(transcript)
        parts.append("")

    # Current suggestions — LLM should update/remove these
    if session.suggestions:
        parts.append("## Your Current Suggestions (remove any that were already addressed above)")
        for s in session.suggestions:
            parts.append(f"- [{s.category}] {s.suggestion}")
        parts.append("")

    if not transcript:
        parts.append("(Meeting just started — no transcript yet. Suggest initial questions based on the documents.)")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
