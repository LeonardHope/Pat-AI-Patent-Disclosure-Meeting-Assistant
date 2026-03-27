"""Unified LLM client interface.

All LLM providers (Ollama, Claude, llama.cpp) implement this protocol.
"""

from typing import AsyncIterator, Protocol


class LLMClient(Protocol):
    """Protocol for LLM providers."""

    async def generate(self, messages: list[dict[str, str]]) -> str:
        """Generate a completion from a list of messages.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": "..."}

        Returns:
            The assistant's response text.
        """
        ...
