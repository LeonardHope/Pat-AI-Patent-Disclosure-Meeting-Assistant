"""Post-meeting summary generation."""

import logging
import time

from ai.prompts.summary_prompt import SUMMARY_PROMPT
from meeting.session import MeetingSession

logger = logging.getLogger(__name__)


def generate_summary_sync(session: MeetingSession, llm_client) -> str:
    """Generate a post-meeting summary synchronously."""
    transcript = session.get_transcript_text()
    if not transcript:
        return "No transcript was captured during this meeting."

    # Keep context compact for fast generation
    doc_context = ""
    if session.document_texts:
        for name, text in zip(session.document_names, session.document_texts):
            doc_context += f"Document: {name}\n{text[:1500]}\n\n"

    user_content = f"{doc_context}## Meeting Transcript\n\n{transcript[:6000]}"

    messages = [
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": user_content},
    ]

    logger.info(f"Generating summary ({len(user_content)} chars context)...")
    t0 = time.monotonic()
    summary = llm_client.generate_sync(messages)
    elapsed = time.monotonic() - t0
    logger.info(f"Summary generated in {elapsed:.1f}s")

    return summary
