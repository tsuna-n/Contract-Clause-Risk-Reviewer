"""Provider adapters: one LLM vendor per backend, chosen by ``LLM_PROVIDER``.

Everything vendor-specific lives here — the SDK import, the request shape, the
usage field names, and each vendor's own spelling of "return JSON matching this
schema". :class:`~app.ai.llm.LLMClient` and the agents above it only ever see
``complete``/``complete_structured``, so switching vendors is an ``.env`` edit
rather than a code change.

Four providers, three backends: ``zai`` is the OpenAI-compatible backend with
Z.AI's endpoint and model pre-filled, because that is the whole difference.
The same backend serves any other OpenAI-shaped API (DeepSeek, Ollama, vLLM)
by setting ``LLM_BASE_URL`` and ``LLM_MODEL``.

SDKs are imported lazily inside ``_get_client`` for the same reason the Gemini
client always was: the app must boot, and the tests must run, on a machine that
has neither the key nor the SDK for a provider it isn't using.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.config import Settings

# --- provider registry -------------------------------------------------------

GEMINI = "gemini"
ANTHROPIC = "anthropic"
OPENAI = "openai"
ZAI = "zai"

PROVIDERS = (GEMINI, ANTHROPIC, OPENAI, ZAI)

#: Model used when ``LLM_MODEL`` is unset. ``openai`` has no entry on purpose:
#: the OpenAI catalogue turns over fast enough that a stale default would fail
#: with a confusing 404 instead of an honest "tell me which model".
_DEFAULT_CHAT_MODELS = {
    GEMINI: "gemini-3.5-flash",
    ANTHROPIC: "claude-opus-5",
    ZAI: "glm-4.6",
}

#: Same, for ``EMBEDDING_MODEL``. Anthropic has no embedding API at all.
_DEFAULT_EMBEDDING_MODELS = {
    GEMINI: "gemini-embedding-001",
    OPENAI: "text-embedding-3-small",
    ZAI: "embedding-3",
}

#: Providers that can embed. ``embedding_provider`` falls back to Gemini when
#: the chat provider isn't one of these, which is what makes "Claude for review,
#: Gemini for retrieval" work without extra configuration.
EMBEDDING_PROVIDERS = (GEMINI, OPENAI, ZAI)

_BASE_URLS = {ZAI: "https://api.z.ai/api/paas/v4"}

#: Which ``.env`` key each provider reads when ``LLM_API_KEY`` isn't set. The
#: per-vendor names are kept because they're what the SDKs and every other tool
#: on the machine already expect.
_API_KEY_FIELDS = {
    GEMINI: "gemini_api_key",
    ANTHROPIC: "anthropic_api_key",
    OPENAI: "openai_api_key",
    ZAI: "zai_api_key",
}

#: Effort levels the Anthropic API accepts. Anything else is dropped rather
#: than passed through, since an unknown value is a 400 for the whole request.
_ANTHROPIC_EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})

#: Which wire protocol each provider speaks. ``openai`` and ``zai`` share one,
#: which is why a GLM model served over an OpenAI-compatible host is a valid
#: pairing and not a mistake.
_BACKEND_FAMILY = {GEMINI: GEMINI, ANTHROPIC: ANTHROPIC, OPENAI: OPENAI, ZAI: OPENAI}

#: Model-name prefixes each provider is known to own. These exist to catch the
#: half-switched ``.env`` - ``LLM_PROVIDER`` moved to Anthropic while
#: ``LLM_MODEL`` still names a Gemini model - which would otherwise surface as
#: a vendor 404 with nothing pointing at the setting that caused it. An
#: unrecognized prefix is left alone: self-hosted and fine-tuned models can be
#: named anything.
_MODEL_PREFIX_OWNERS = (
    (("gemini-",), GEMINI),
    (("claude-",), ANTHROPIC),
    (("gpt-", "text-embedding-", "o1-", "o3-", "o4-"), OPENAI),
)


class ProviderConfigError(RuntimeError):
    """Raised when the configured provider can't be used as described.

    A missing key or an unknown provider name is a deployment mistake, not a
    runtime condition to recover from — it fails on the first call with a
    message naming the ``.env`` field to fix.
    """


# --- usage accounting --------------------------------------------------------


@dataclass
class Usage:
    """Accumulated token usage for cost tracking.

    Normalized across vendors: each backend maps its own field names onto
    these three so the pipeline's cost numbers mean the same thing regardless
    of who served the request.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens


# --- backend protocol --------------------------------------------------------


class ChatBackend(Protocol):
    """What every provider adapter has to offer the agents above it."""

    model: str

    def complete(
        self, *, system: str, prompt: str, max_tokens: int, effort: str
    ) -> tuple[str, Usage]:
        """Run a single completion, returning the text and what it cost."""
        ...

    def complete_structured[T: BaseModel](
        self, *, system: str, prompt: str, response_model: type[T], max_tokens: int
    ) -> tuple[T, Usage]:
        """Return a validated ``response_model`` instance and what it cost."""
        ...


# --- gemini ------------------------------------------------------------------


class GeminiChatBackend:
    """Google GenAI (Gemini) via ``google-genai``."""

    def __init__(self, *, model: str, api_key: str | None, timeout_seconds: int) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = None  # lazily constructed google.genai.Client

    def _get_client(self):
        """Lazily construct the underlying ``google.genai.Client``."""
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                # HttpOptions.timeout is milliseconds. Set on the client so it
                # covers every call made through it, structured output included.
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            )
        return self._client

    @staticmethod
    def _usage(response) -> Usage:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return Usage()
        return Usage(
            input_tokens=meta.prompt_token_count or 0,
            output_tokens=meta.candidates_token_count or 0,
            cache_read_input_tokens=meta.cached_content_token_count or 0,
        )

    def complete(
        self, *, system: str, prompt: str, max_tokens: int, effort: str
    ) -> tuple[str, Usage]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=effort.upper()) if effort else None,
        )
        response = self._get_client().models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response.text or "", self._usage(response)

    def complete_structured[T: BaseModel](
        self, *, system: str, prompt: str, response_model: type[T], max_tokens: int
    ) -> tuple[T, Usage]:
        from google.genai import types

        response = self._get_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=response_model,
            ),
        )
        parsed = response.parsed
        if isinstance(parsed, response_model):
            return parsed, self._usage(response)
        return response_model.model_validate_json(response.text), self._usage(response)


# --- anthropic ---------------------------------------------------------------


class AnthropicChatBackend:
    """Anthropic (Claude) via the official ``anthropic`` SDK.

    Structured output goes through ``messages.parse``, which constrains the
    response to the schema and hands back a validated model instance — the same
    contract Gemini's ``response_schema`` gives us, so the judge's guardrails
    don't have to care which one produced the answer.
    """

    def __init__(
        self, *, model: str, api_key: str | None, base_url: str | None, timeout_seconds: int
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = None  # lazily constructed anthropic.Anthropic
        self._supports_effort = True

    def _get_client(self):
        """Lazily construct the underlying ``anthropic.Anthropic`` client."""
        if self._client is None:
            import anthropic

            # The Anthropic SDK takes seconds, not milliseconds like Gemini.
            kwargs: dict[str, Any] = {"api_key": self._api_key, "timeout": self._timeout_seconds}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    @staticmethod
    def _usage(response) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage()
        return Usage(
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )

    def _message(self, *, system: str, prompt: str, max_tokens: int, output_config: Any | None):
        kwargs: dict[str, Any] = {}
        if output_config is not None:
            kwargs["output_config"] = output_config
        return self._get_client().messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )

    def complete(
        self, *, system: str, prompt: str, max_tokens: int, effort: str
    ) -> tuple[str, Usage]:
        response = None
        if effort in _ANTHROPIC_EFFORT_LEVELS and self._supports_effort:
            try:
                response = self._message(
                    system=system,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    output_config={"effort": effort},
                )
            except Exception:  # noqa: BLE001 - smaller/older models reject `effort`
                # Haiku 4.5 and the 4.5-era Sonnet 400 on `output_config`, and
                # which models accept it shifts with each release - so the
                # answer is asked once and remembered rather than hard-coded
                # into a list that goes stale.
                self._supports_effort = False

        if response is None:
            response = self._message(
                system=system, prompt=prompt, max_tokens=max_tokens, output_config=None
            )

        # A refusal is a 200 with an empty content list, not an exception; the
        # orchestrator already degrades an empty answer to "needs manual
        # review", so returning "" is the honest thing to hand back.
        text = "".join(block.text for block in response.content if block.type == "text")
        return text, self._usage(response)

    def complete_structured[T: BaseModel](
        self, *, system: str, prompt: str, response_model: type[T], max_tokens: int
    ) -> tuple[T, Usage]:
        response = self._get_client().messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=response_model,
        )
        parsed = response.parsed_output
        if isinstance(parsed, response_model):
            return parsed, self._usage(response)
        # ``parsed_output`` is None when the model stops early (max_tokens, a
        # refusal); re-validate the raw text so the caller sees a pydantic
        # error naming the missing field rather than an AttributeError on None.
        text = "".join(block.text for block in response.content if block.type == "text")
        return response_model.model_validate_json(text), self._usage(response)


# --- openai-compatible (OpenAI, Z.AI/GLM, DeepSeek, Ollama, vLLM, ...) --------


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a pydantic schema into the strict subset OpenAI validates.

    Strict mode wants every object closed (``additionalProperties: false``) and
    every property listed in ``required`` — optional fields are expressed as a
    nullable type instead. Pydantic emits neither, so we walk the schema and
    add them; ``$defs`` are walked too, since nested models live there.
    """
    if not isinstance(schema, dict):
        return schema

    out = {key: value for key, value in schema.items()}
    if out.get("type") == "object":
        properties = out.get("properties") or {}
        out["properties"] = {name: _strict_json_schema(sub) for name, sub in properties.items()}
        out["required"] = list(properties)
        out["additionalProperties"] = False
    if "items" in out:
        out["items"] = _strict_json_schema(out["items"])
    for key in ("$defs", "definitions"):
        if key in out:
            out[key] = {name: _strict_json_schema(sub) for name, sub in out[key].items()}
    for key in ("anyOf", "oneOf", "allOf"):
        if key in out:
            out[key] = [_strict_json_schema(sub) for sub in out[key]]
    return out


class OpenAICompatibleChatBackend:
    """Any OpenAI-shaped chat completions API, including Z.AI's GLM models.

    Structured output is the one place these endpoints disagree: OpenAI
    validates a full ``json_schema``, while several compatible hosts only
    implement ``json_object``. Rather than maintain a per-host capability
    table that goes stale, the first structured call tries the strict schema
    and remembers a rejection, falling back to JSON mode with the schema
    inlined in the system prompt. Either way pydantic validates the result, so
    the guardrails downstream see the same contract.
    """

    def __init__(
        self, *, model: str, api_key: str | None, base_url: str | None, timeout_seconds: int
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = None  # lazily constructed openai.OpenAI
        self._supports_json_schema = True

    def _get_client(self):
        """Lazily construct the underlying ``openai.OpenAI`` client."""
        if self._client is None:
            import openai

            # The OpenAI SDK takes seconds, like Anthropic's.
            self._client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            )
        return self._client

    @staticmethod
    def _usage(response) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage()
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details is not None else 0
        return Usage(
            input_tokens=usage.prompt_tokens or 0,
            output_tokens=usage.completion_tokens or 0,
            cache_read_input_tokens=cached or 0,
        )

    def _chat(self, *, system: str, prompt: str, max_tokens: int, response_format: Any | None):
        kwargs: dict[str, Any] = {}
        if response_format is not None:
            kwargs["response_format"] = response_format
        return self._get_client().chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )

    def complete(
        self, *, system: str, prompt: str, max_tokens: int, effort: str
    ) -> tuple[str, Usage]:
        # No portable effort/thinking control across these hosts - the ones
        # that expose it all spell it differently, so it's left to the model's
        # own default rather than guessed at.
        response = self._chat(
            system=system, prompt=prompt, max_tokens=max_tokens, response_format=None
        )
        return response.choices[0].message.content or "", self._usage(response)

    def complete_structured[T: BaseModel](
        self, *, system: str, prompt: str, response_model: type[T], max_tokens: int
    ) -> tuple[T, Usage]:
        schema = _strict_json_schema(response_model.model_json_schema())

        if self._supports_json_schema:
            try:
                response = self._chat(
                    system=system,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_model.__name__,
                            "schema": schema,
                            "strict": True,
                        },
                    },
                )
                return self._parse(response, response_model)
            except Exception:  # noqa: BLE001 - host may not implement json_schema
                # Remembered so the whole pipeline pays this probe once, not
                # once per clause. A network failure lands here too and is
                # re-raised by the JSON-mode attempt below.
                self._supports_json_schema = False

        response = self._chat(
            system=(
                f"{system}\n\n"
                "Respond with a single JSON object and nothing else - no prose, no code fences. "
                f"It must validate against this JSON Schema:\n{json.dumps(schema)}"
            ),
            prompt=prompt,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return self._parse(response, response_model)

    @staticmethod
    def _parse[T: BaseModel](response, response_model: type[T]) -> tuple[T, Usage]:
        text = response.choices[0].message.content or ""
        return (
            response_model.model_validate_json(text),
            OpenAICompatibleChatBackend._usage(response),
        )


# --- selection ---------------------------------------------------------------


def resolve_provider(name: str | None, *, field: str) -> str:
    """Normalize and validate a provider name from settings."""
    provider = (name or GEMINI).strip().lower()
    if provider not in PROVIDERS:
        raise ProviderConfigError(
            f"unknown provider {provider!r} in {field}; expected one of {', '.join(PROVIDERS)}"
        )
    return provider


def resolve_api_key(settings: Settings, provider: str, *, override: str | None) -> str | None:
    """Return the key for ``provider``: the explicit override, else its own env var.

    A blank value counts as unset. ``FOO_API_KEY=`` with nothing after it is
    what a half-finished ``.env`` edit looks like, and every SDK here accepts
    the empty string at construction and only fails later with a 401 per call.
    """
    for candidate in (override, getattr(settings, _API_KEY_FIELDS[provider], None)):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def require_api_key(settings: Settings, provider: str, *, override: str | None) -> str:
    """Return the key for ``provider`` or say which ``.env`` field is missing."""
    key = resolve_api_key(settings, provider, override=override)
    if key is None:
        env_name = _API_KEY_FIELDS[provider].upper()
        raise ProviderConfigError(
            f"{env_name} is not set, so provider {provider!r} can't authenticate; "
            f"set {env_name} (or LLM_API_KEY) in .env"
        )
    return key


def _reject_mismatched_model(model: str, provider: str, *, field: str, default: str | None) -> None:
    """Fail fast when a model name belongs to a different vendor than ``provider``.

    Switching ``LLM_PROVIDER`` while leaving ``LLM_MODEL`` behind is the easy
    mistake to make, and the vendor's own answer to it is a bare 404 that says
    nothing about which setting is stale.
    """
    owner = next(
        (owner for prefixes, owner in _MODEL_PREFIX_OWNERS if model.startswith(prefixes)),
        None,
    )
    if owner is None or _BACKEND_FAMILY[owner] == _BACKEND_FAMILY[provider]:
        return
    remedy = f" (or unset it to use {default})" if default else ""
    raise ProviderConfigError(
        f"{field}={model!r} is a {owner} model but the provider is {provider}; "
        f"set {field} to a model served by {provider}{remedy}"
    )


def resolve_chat_model(provider: str, configured: str | None) -> str:
    """Return the chat model for ``provider``, or explain what to set."""
    default = _DEFAULT_CHAT_MODELS.get(provider)
    if configured:
        _reject_mismatched_model(configured, provider, field="LLM_MODEL", default=default)
        return configured
    if default is None:
        raise ProviderConfigError(f"LLM_MODEL must be set when LLM_PROVIDER={provider}")
    return default


def resolve_embedding_model(provider: str, configured: str | None) -> str:
    """Return the embedding model for ``provider``, or explain what to set."""
    default = _DEFAULT_EMBEDDING_MODELS.get(provider)
    if configured:
        _reject_mismatched_model(configured, provider, field="EMBEDDING_MODEL", default=default)
        return configured
    if default is None:
        raise ProviderConfigError(
            f"{provider} has no embedding API; set EMBEDDING_PROVIDER to one of "
            f"{', '.join(EMBEDDING_PROVIDERS)}"
        )
    return default


def resolve_base_url(provider: str, configured: str | None) -> str | None:
    """Return the API host: an explicit override, else the provider's own."""
    return configured or _BASE_URLS.get(provider)


def resolve_embedding_provider(settings: Settings) -> str:
    """Return the provider to embed with.

    Defaults to the chat provider so a single-vendor setup needs one setting,
    but falls back to Gemini when that vendor can't embed — which is how
    "Claude reviews, Gemini retrieves" works with nothing extra configured.
    """
    if settings.embedding_provider:
        return resolve_provider(settings.embedding_provider, field="EMBEDDING_PROVIDER")
    chat_provider = resolve_provider(settings.llm_provider, field="LLM_PROVIDER")
    return chat_provider if chat_provider in EMBEDDING_PROVIDERS else GEMINI


def build_chat_backend(
    settings: Settings, *, model: str | None = None, timeout_seconds: int | None = None
) -> ChatBackend:
    """Construct the chat backend described by ``settings``."""
    provider = resolve_provider(settings.llm_provider, field="LLM_PROVIDER")
    resolved_model = model or resolve_chat_model(provider, settings.llm_model)
    api_key = require_api_key(settings, provider, override=settings.llm_api_key)
    base_url = resolve_base_url(provider, settings.llm_base_url)
    timeout = timeout_seconds or settings.llm_timeout_seconds

    if provider == GEMINI:
        return GeminiChatBackend(
            model=resolved_model, api_key=api_key, timeout_seconds=timeout
        )
    if provider == ANTHROPIC:
        return AnthropicChatBackend(
            model=resolved_model, api_key=api_key, base_url=base_url, timeout_seconds=timeout
        )
    return OpenAICompatibleChatBackend(
        model=resolved_model, api_key=api_key, base_url=base_url, timeout_seconds=timeout
    )
