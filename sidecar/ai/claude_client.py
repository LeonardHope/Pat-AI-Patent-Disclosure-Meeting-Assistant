"""Unified LLM client using Anthropic SDK.

Works with both:
- LM Studio (local): Anthropic-compatible endpoint at localhost:1234
- Claude API (cloud): Anthropic's API at api.anthropic.com

Same SDK, same code, different base_url.
"""

import logging
import httpx

logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    """LLM client using the Anthropic SDK for both local and cloud."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        api_key: str = "lmstudio",
        model: str = "",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._sync_client = httpx.Client(base_url=self.base_url, timeout=120.0)
        self._api_key = api_key

    def generate_sync(self, messages: list[dict[str, str]]) -> str:
        """Synchronous generation via Anthropic-compatible /v1/messages."""
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                chat_messages.append(msg)

        payload = {
            "model": self.model or "default",
            "max_tokens": 2048,
            "temperature": 0.3,
            "messages": chat_messages,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            response = self._sync_client.post(
                "/v1/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Anthropic format: {"content": [{"type": "text", "text": "..."}]}
            content = data.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return str(data)

        except httpx.ConnectError:
            logger.error(f"Cannot connect to LLM at {self.base_url}. Is LM Studio / Claude API running?")
            return "[]"
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error {e.response.status_code}: {e.response.text[:200]}")
            return "[]"
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "[]"

    async def generate(self, messages: list[dict[str, str]]) -> str:
        """Async wrapper — delegates to sync."""
        return self.generate_sync(messages)

    def is_available(self) -> bool:
        """Check if the LLM endpoint is reachable."""
        try:
            r = self._sync_client.get("/v1/models", timeout=3)
            return r.status_code == 200
        except Exception:
            return False
