"""Suggestion loop — debounces transcript updates and calls the LLM.

Runs as an asyncio task during an active meeting. Watches for new
transcript segments and triggers LLM calls at appropriate intervals
using debouncing, keyword triggers, and rate limiting.
"""

import asyncio
import json
import logging
import re
import time
import uuid

from ai.context_builder import build_suggestion_prompt


def _sync_llm_call(llm, messages):
    """Call LLM.generate_sync (for use in thread executor)."""
    try:
        return llm.generate_sync(messages)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return "[]"
from ai.llm_client import LLMClient
from meeting.session import MeetingSession, Suggestion

logger = logging.getLogger(__name__)

# Keyword phrases that indicate the inventor is explaining something important
KEYWORD_TRIGGERS = [
    r"the way it works",
    r"what's different",
    r"the key (?:thing|innovation|idea)",
    r"the problem (?:we're|we are) solving",
    r"our approach",
    r"the novel(?:ty)?",
    r"compared to",
    r"unlike (?:existing|current|previous)",
    r"the advantage",
    r"preferred (?:embodiment|implementation|way)",
]
_keyword_pattern = re.compile("|".join(KEYWORD_TRIGGERS), re.IGNORECASE)


class SuggestionLoop:
    """Manages the LLM suggestion generation loop."""

    def __init__(
        self,
        session: MeetingSession,
        llm_client: LLMClient,
        on_suggestions_update,  # callable(list[Suggestion]) -> None
        debounce_seconds: float = 8.0,
        min_interval_seconds: float = 8.0,
        max_suggestions: int = 5,
    ):
        self.session = session
        self.llm = llm_client
        self.on_suggestions_update = on_suggestions_update
        self.debounce_seconds = debounce_seconds
        self.min_interval_seconds = min_interval_seconds
        self.max_suggestions = max_suggestions

        self._task: asyncio.Task | None = None
        self._last_call_time: float = 0
        self._last_transcript_len: int = 0
        self._trigger_event = asyncio.Event()
        self._running = False

    def start(self) -> None:
        """Start the suggestion loop."""
        self._running = True
        self._trigger_event.clear()
        self._task = asyncio.ensure_future(self._loop())
        logger.info("Suggestion loop started")

    def stop(self) -> None:
        """Stop the suggestion loop."""
        self._running = False
        self._trigger_event.set()  # Unblock any waiting
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Suggestion loop stopped")

    def on_new_segment(self, text: str) -> None:
        """Called when a new transcript segment arrives. May trigger immediate LLM call."""
        if _keyword_pattern.search(text):
            logger.info(f"Keyword trigger detected in: {text[:50]}...")
            self._trigger_event.set()

    async def _loop(self) -> None:
        """Main loop: wait for debounce, then call LLM."""
        while self._running:
            try:
                # Wait for either debounce timeout or keyword trigger
                try:
                    await asyncio.wait_for(
                        self._trigger_event.wait(),
                        timeout=self.debounce_seconds,
                    )
                    self._trigger_event.clear()
                except asyncio.TimeoutError:
                    pass  # Debounce expired — check if we should call

                if not self._running:
                    break

                # Rate limit
                elapsed = time.monotonic() - self._last_call_time
                if elapsed < self.min_interval_seconds:
                    await asyncio.sleep(self.min_interval_seconds - elapsed)

                # Skip if no new transcript
                current_len = len(self.session.transcript)
                if current_len == self._last_transcript_len:
                    continue
                self._last_transcript_len = current_len

                # Call LLM
                await self._generate_suggestions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Suggestion loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def _generate_suggestions(self) -> None:
        """Call the LLM and update suggestions."""
        self._last_call_time = time.monotonic()

        messages = build_suggestion_prompt(
            self.session,
            max_suggestions=self.max_suggestions,
        )

        logger.info("Calling LLM for suggestions...")
        t0 = time.monotonic()
        # Run LLM in thread to not block the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: _sync_llm_call(self.llm, messages)
        )
        elapsed = time.monotonic() - t0
        logger.info(f"LLM responded in {elapsed:.1f}s")

        # Parse JSON response
        suggestions = self._parse_suggestions(response)
        if suggestions:
            self.session.update_suggestions(suggestions)
            self.on_suggestions_update(suggestions)

    def _parse_suggestions(self, response: str) -> list[Suggestion]:
        """Parse the LLM's JSON response into Suggestion objects."""
        import re
        text = response.strip()

        # Strip thinking text (Qwen 3.5 outputs reasoning before JSON)
        bracket = text.find("[")
        if bracket > 0:
            text = text[bracket:]

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        text = text.strip()

        # Fix common JSON errors
        text = re.sub(r',\s*]', ']', text)
        text = re.sub(r',\s*}', '}', text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    cleaned = re.sub(r',\s*]', ']', text[start:end])
                    cleaned = re.sub(r',\s*}', '}', cleaned)
                    data = json.loads(cleaned)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM response as JSON: {text[:200]}")
                    return []
            else:
                logger.warning(f"No JSON array found in LLM response: {text[:200]}")
                return []

        if not isinstance(data, list):
            return []

        suggestions = []
        for item in data[:self.max_suggestions]:
            try:
                suggestions.append(Suggestion(
                    id=item.get("id", uuid.uuid4().hex[:8]),
                    category=item.get("category", "FOLLOW_UP"),
                    priority=item.get("priority", "MEDIUM"),
                    suggestion=item.get("suggestion", ""),
                    context=item.get("context", ""),
                    timestamp=time.monotonic() - self.session.start_time,
                ))
            except Exception:
                continue

        return suggestions
