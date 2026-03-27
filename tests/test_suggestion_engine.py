"""Test the suggestion engine with a mock LLM.

Since Ollama may not be running during testing, this test uses a mock LLM
that returns realistic patent-specific suggestions to verify the full pipeline:
context builder → LLM call → JSON parsing → suggestion update → broadcast.

Usage:
    cd sidecar && uv run python ../tests/test_suggestion_engine.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "sidecar"))

from ai.context_builder import build_suggestion_prompt
from ai.suggestion_loop import SuggestionLoop
from meeting.session import MeetingSession, Suggestion
from transcription.segment import TranscriptSegment


class MockLLMClient:
    """Mock LLM that returns realistic patent suggestions."""

    call_count = 0

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.call_count += 1
        # Extract transcript to tailor response
        user_msg = messages[-1]["content"] if messages else ""

        if "compression" in user_msg.lower():
            return json.dumps([
                {
                    "id": "s1",
                    "category": "ENABLEMENT",
                    "priority": "HIGH",
                    "suggestion": "What specific compression algorithm is used? Is it lossless or lossy? What compression ratios are typically achieved?",
                    "context": "A PHOSITA needs the specific algorithm to reproduce the invention."
                },
                {
                    "id": "s2",
                    "category": "TECHNICAL_DETAIL",
                    "priority": "MEDIUM",
                    "suggestion": "What data formats does the compression support? Are there any constraints on input data types?",
                    "context": "Needed for complete written description of the invention."
                },
            ])
        else:
            return json.dumps([
                {
                    "id": "s1",
                    "category": "ENABLEMENT",
                    "priority": "HIGH",
                    "suggestion": "Can you describe the overall system architecture? How do the components interact?",
                    "context": "A high-level architecture is needed before diving into specifics."
                },
                {
                    "id": "s2",
                    "category": "PRIOR_ART",
                    "priority": "MEDIUM",
                    "suggestion": "What existing solutions have you looked at? How does your approach differ?",
                    "context": "Understanding the prior art landscape is crucial for claim differentiation."
                },
                {
                    "id": "s3",
                    "category": "BEST_MODE",
                    "priority": "LOW",
                    "suggestion": "Of the approaches you've tried, which one works best in practice?",
                    "context": "Best mode disclosure is required under 35 USC 112."
                },
            ])


async def main():
    print("=" * 60)
    print("Suggestion Engine Test (Mock LLM)")
    print("=" * 60)
    print()

    # 1. Test context builder
    print("1. Testing context builder...")
    session = MeetingSession()
    session.start()

    # Add some transcript segments
    segments = [
        TranscriptSegment(text="We've developed a new data compression system.", speaker="REMOTE", timestamp=0.0, duration=2.0),
        TranscriptSegment(text="Can you tell me more about that?", speaker="LOCAL", timestamp=2.5, duration=1.5),
        TranscriptSegment(text="It uses a novel algorithm that achieves 10x compression on structured data.", speaker="REMOTE", timestamp=5.0, duration=3.0),
        TranscriptSegment(text="The system processes data in real-time through a pipeline.", speaker="REMOTE", timestamp=9.0, duration=2.5),
    ]
    for seg in segments:
        session.add_segment(seg)

    messages = build_suggestion_prompt(session, max_suggestions=5)
    assert len(messages) == 2, "Should have system + user messages"
    assert "enablement" in messages[0]["content"].lower(), "System prompt should mention enablement"
    assert "compression" in messages[1]["content"].lower(), "User message should include transcript"
    print("   Context builder OK")
    print(f"   System prompt: {len(messages[0]['content'])} chars")
    print(f"   User context:  {len(messages[1]['content'])} chars")
    print()

    # 2. Test suggestion loop with mock LLM
    print("2. Testing suggestion loop...")
    mock_llm = MockLLMClient()
    received_suggestions = []

    def on_update(suggestions):
        received_suggestions.extend(suggestions)
        for s in suggestions:
            print(f"   [{s.category:18s}] [{s.priority:6s}] {s.suggestion[:70]}...")

    loop = SuggestionLoop(
        session=session,
        llm_client=mock_llm,
        on_suggestions_update=on_update,
        debounce_seconds=1.0,  # Short for testing
        min_interval_seconds=1.0,
        max_suggestions=5,
    )

    loop.start()

    # Wait for debounce + LLM call
    await asyncio.sleep(3)

    # Add more transcript to trigger another call
    session.add_segment(TranscriptSegment(
        text="The key innovation is the way it works with streaming data.",
        speaker="REMOTE", timestamp=12.0, duration=2.0,
    ))
    loop.on_new_segment("The key innovation is the way it works with streaming data.")

    await asyncio.sleep(3)

    loop.stop()

    print(f"\n   Mock LLM called {mock_llm.call_count} times")
    print(f"   Total suggestions received: {len(received_suggestions)}")
    print(f"   Session suggestions: {len(session.suggestions)}")
    print()

    # 3. Test JSON parsing with edge cases
    print("3. Testing JSON parsing edge cases...")
    loop2 = SuggestionLoop(
        session=session, llm_client=mock_llm,
        on_suggestions_update=lambda x: None,
    )

    # Normal JSON
    result = loop2._parse_suggestions('[{"id":"s1","category":"ENABLEMENT","priority":"HIGH","suggestion":"test","context":"ctx"}]')
    assert len(result) == 1, "Should parse normal JSON"

    # JSON in markdown code block
    result = loop2._parse_suggestions('```json\n[{"id":"s1","category":"ENABLEMENT","priority":"HIGH","suggestion":"test","context":"ctx"}]\n```')
    assert len(result) == 1, "Should parse markdown-wrapped JSON"

    # Empty/invalid
    result = loop2._parse_suggestions("I can't help with that.")
    assert len(result) == 0, "Should handle non-JSON gracefully"

    result = loop2._parse_suggestions("[]")
    assert len(result) == 0, "Should handle empty array"

    print("   JSON parsing OK")
    print()

    # 4. Test with documents
    print("4. Testing with document context...")
    session.document_names.append("invention_disclosure.pdf")
    session.document_texts.append("Title: Novel Data Compression System\n\nThe invention relates to a real-time data compression system that achieves 10x compression ratios on structured data using a novel streaming algorithm.")

    messages = build_suggestion_prompt(session, max_suggestions=5)
    assert "invention_disclosure.pdf" in messages[1]["content"], "Should include document name"
    assert "compression" in messages[1]["content"].lower(), "Should include document content"
    print("   Document context included OK")
    print()

    # Summary
    print("=" * 60)
    assert mock_llm.call_count >= 2, f"Expected >= 2 LLM calls, got {mock_llm.call_count}"
    assert len(received_suggestions) >= 2, f"Expected >= 2 suggestions, got {len(received_suggestions)}"
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
