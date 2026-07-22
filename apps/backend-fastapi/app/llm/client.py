"""Google GenAI (Gemini) client wrapper: retry, timeout, cost tracking."""

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
    """Thin wrapper over the Google GenAI SDK (Gemini models).

    Centralizes model selection, retries/timeouts, and usage accounting so the
    agents don't each re-implement it. The SDK retries transient errors
    automatically; this wrapper adds cost tracking and a single place to set
    defaults.
    """

    def __init__(self, model: str | None = None, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self._api_key = settings.gemini_api_key
        self._timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.usage = Usage()
        self._client = None  # lazily constructed google.genai.Client

    def _get_client(self):
        """Lazily construct the underlying ``google.genai.Client``."""
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                # HttpOptions.timeout is milliseconds. Set on the client so it
                # covers every call made through it, including the structured
                # -output path in app.llm.structured.
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            )
        return self._client

    def _record_usage(self, response) -> None:
        """Accumulate ``response.usage_metadata`` into :attr:`usage`."""
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        self.usage.add(
            Usage(
                input_tokens=meta.prompt_token_count or 0,
                output_tokens=meta.candidates_token_count or 0,
                cache_read_input_tokens=meta.cached_content_token_count or 0,
            )
        )

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 4096,
        effort: str = "high",
    ) -> str:
        """Run a single completion and return the text."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=effort.upper())
            if effort
            else None,
        )
        response = self._get_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        self._record_usage(response)
        return response.text or ""
