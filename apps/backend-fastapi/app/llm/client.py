"""Anthropic Claude client wrapper: retry, timeout, cost tracking."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class Usage:
    """Accumulated token usage for cost tracking."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens


class LLMClient:
    """Thin wrapper over the Anthropic SDK.

    Centralizes model selection, retries/timeouts, and usage accounting so the
    agents don't each re-implement it. The SDK retries 429/5xx automatically;
    this wrapper adds cost tracking and a single place to set defaults.
    """

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self._api_key = settings.anthropic_api_key
        self.usage = Usage()
        self._client = None  # lazily constructed anthropic.Anthropic

    def _get_client(self):
        """Lazily construct the underlying ``anthropic.Anthropic`` client."""
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 4096,
        effort: str = "high",
    ) -> str:
        """Run a single completion and return the text.

        TODO: call ``client.messages.create`` with adaptive thinking, accumulate
        ``response.usage`` into ``self.usage``, and return the joined text blocks.
        """
        raise NotImplementedError
