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
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

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

#: Same, for ``EMBEDDING_MODEL``. Two providers are absent: Anthropic has no
#: embedding API at all, and ``api.z.ai`` serves chat models only — its
#: ``/models`` list is eight GLM entries with no ``embedding-*`` among them, and
#: asking for one answers ``400 code 1211 Unknown Model``. The ``embedding-2``
#: and ``embedding-3`` names belong to Zhipu's separate BigModel platform, so
#: reaching them takes an explicit ``EMBEDDING_MODEL`` and ``EMBEDDING_BASE_URL``
#: rather than a default that only works for some accounts.
_DEFAULT_EMBEDDING_MODELS = {
    GEMINI: "gemini-embedding-001",
    OPENAI: "text-embedding-3-small",
}

#: Providers that can embed with nothing configured beyond a key.
#: ``embedding_provider`` falls back to Gemini when the chat provider isn't one
#: of these, which is what makes "Claude (or GLM) for review, Gemini for
#: retrieval" work without extra configuration.
EMBEDDING_PROVIDERS = (GEMINI, OPENAI)

#: Why a provider has no default embedding model, in the words the error uses.
_NO_EMBEDDING_MODEL_REASONS = {
    ANTHROPIC: "has no embedding API",
    ZAI: "serves no embedding model on api.z.ai",
}

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


class EmptyCompletionError(RuntimeError):
    """Raised when a call returns a 200 with no text to parse.

    Its own type because it is retryable and because the pydantic error it
    replaces (``Invalid JSON: EOF while parsing a value``) named the schema
    rather than the reason. The two causes are a refusal and, far more often on
    a reasoning model, a turn that spent its whole ``max_tokens`` budget
    thinking and had nothing left to answer with.
    """


#: Exception type names that mean "ask again", across vendors. Matched by name
#: because the alternative is importing three SDKs at call time to catch their
#: classes — and every one of these is the same thing wearing a different label.
_TRANSIENT_ERROR_NAMES = (
    "timeout",  # openai APITimeoutError, anthropic APITimeoutError
    "connection",  # APIConnectionError
    "ratelimit",  # 429 with a retry-after
    "resourceexhausted",  # gemini's spelling of 429
    "internalserver",  # 5xx
    "serviceunavailable",
    "unavailable",
    "overloaded",  # anthropic 529
    "deadlineexceeded",  # gemini's spelling of a timeout
    "servererror",  # google.genai.errors.ServerError
)

#: HTTP statuses worth another attempt. 400/401/403/404 are not here on
#: purpose: a bad request or a bad key answers the same way however many times
#: it is asked, and retrying only delays the message that says so.
_TRANSIENT_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})


def is_malformed_answer(exc: BaseException) -> bool:
    """Whether ``exc`` means the host answered, just not with what was asked for.

    Worth its own predicate because it is the one failure that says something
    about the *host* rather than about the network: a request that came back
    200 carrying prose is how a host that ignores ``response_format`` announces
    itself, which is what the fallback in
    :meth:`OpenAICompatibleChatBackend.complete_structured` turns on.
    """
    return isinstance(exc, EmptyCompletionError | ValidationError)


def is_transient(exc: BaseException) -> bool:
    """Whether ``exc`` is the kind of failure a second attempt could survive.

    Vendor knowledge belongs in this module, so the retry loop in
    :mod:`app.ai.llm` asks this instead of knowing which SDK raised what.

    A malformed answer counts: output is sampled, so it is a roll of the dice
    rather than a verdict on the schema, and the price of not asking again is a
    clause that reads ``unknown`` in the report.
    """
    if is_malformed_answer(exc):
        return True
    for attr in ("status_code", "code"):
        status = getattr(exc, attr, None)
        if isinstance(status, int) and status in _TRANSIENT_STATUS_CODES:
            return True
    name = type(exc).__name__.lower()
    return any(marker in name for marker in _TRANSIENT_ERROR_NAMES)


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
        # Clauses review concurrently (see ``review_concurrency``), so the
        # first call of a run can reach this from several threads before
        # ``_client`` is set - the lock makes construction happen once instead
        # of once per thread that got there first.
        self._client_lock = threading.Lock()

    def _get_client(self):
        """Lazily construct the underlying ``google.genai.Client``."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    from google import genai
                    from google.genai import types

                    self._client = genai.Client(
                        api_key=self._api_key,
                        # HttpOptions.timeout is milliseconds. Set on the client
                        # so it covers every call made through it, structured
                        # output included.
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
        text = response.text or ""
        if not text.strip():
            # ``parsed`` is None with no text when the turn was blocked or
            # stopped at ``max_output_tokens``. ``response.text`` is None there
            # rather than "", which pydantic answers with a TypeError.
            candidates = getattr(response, "candidates", None) or []
            reason = getattr(candidates[0], "finish_reason", None) if candidates else None
            raise EmptyCompletionError(
                f"{response_model.__name__}: model returned no content (finish_reason={reason!r})"
            )
        return response_model.model_validate_json(_json_object(text)), self._usage(response)


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
        self._client_lock = threading.Lock()

    def _get_client(self):
        """Lazily construct the underlying ``anthropic.Anthropic`` client."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    import anthropic

                    # The Anthropic SDK takes seconds, not milliseconds like Gemini.
                    kwargs: dict[str, Any] = {
                        "api_key": self._api_key,
                        "timeout": self._timeout_seconds,
                    }
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
        if not text.strip():
            raise EmptyCompletionError(
                f"{response_model.__name__}: model returned no content "
                f"(stop_reason={getattr(response, 'stop_reason', None)!r})"
            )
        return response_model.model_validate_json(_json_object(text)), self._usage(response)


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


def _json_object(text: str) -> str:
    """Return the outermost JSON object in ``text``.

    JSON mode is a request, not a guarantee: hosts that only implement
    ``json_object`` still hand back ```` ```json ```` fences or a line of
    prose before the brace often enough to matter over a few hundred calls.
    Text with no brace at all is returned untouched so pydantic reports the
    real content rather than a slice of it.
    """
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


class OpenAICompatibleChatBackend:
    """Any OpenAI-shaped chat completions API, including Z.AI's GLM models.

    Structured output is the one place these endpoints disagree: OpenAI
    validates a full ``json_schema``, while several compatible hosts only
    implement ``json_object``. Rather than maintain a per-host capability
    table that goes stale, the first structured call tries the strict schema
    and remembers a rejection, falling back to JSON mode with the schema
    inlined in the system prompt. Either way pydantic validates the result, so
    the guardrails downstream see the same contract.

    ``disable_thinking`` asks a reasoning model to answer directly. It matters
    more than it sounds: reasoning tokens are billed and counted inside the
    same ``max_tokens`` budget as the answer, so a model that thinks too long
    returns a 200 with empty ``content``. Measured on GLM-4.6 with one of this
    pipeline's own scoring prompts, the same call took 23.7s and 984 output
    tokens thinking versus 2.1s and 55 without.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None,
        timeout_seconds: int,
        disable_thinking: bool = False,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = None  # lazily constructed openai.OpenAI
        self._supports_json_schema = True
        self._disable_thinking = disable_thinking
        self._supports_thinking_param = True
        self._client_lock = threading.Lock()

    def _get_client(self):
        """Lazily construct the underlying ``openai.OpenAI`` client."""
        if self._client is None:
            with self._client_lock:
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

    def _create(self, *, system: str, prompt: str, max_tokens: int, **kwargs: Any):
        return self._get_client().chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )

    def _chat(self, *, system: str, prompt: str, max_tokens: int, response_format: Any | None):
        kwargs: dict[str, Any] = {}
        if response_format is not None:
            kwargs["response_format"] = response_format

        # ``thinking`` is Z.AI's parameter, not part of the OpenAI schema, so a
        # host that has never heard of it answers 400. Same probe-and-remember
        # shape as ``json_schema`` above - asked once per backend, not once per
        # clause - except a transient failure is re-raised rather than read as
        # "unsupported", or one timeout would switch thinking back on for the
        # rest of the run and cause the next one.
        sending_thinking = self._disable_thinking and self._supports_thinking_param
        if sending_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            return self._create(system=system, prompt=prompt, max_tokens=max_tokens, **kwargs)
        except Exception as exc:
            if not sending_thinking or is_transient(exc):
                raise
            self._supports_thinking_param = False
            kwargs.pop("extra_body")
            return self._create(system=system, prompt=prompt, max_tokens=max_tokens, **kwargs)

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
        probing = self._supports_json_schema

        if probing:
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
            except Exception as exc:
                # Two ways a host says it can't do this: rejecting the parameter
                # (a 400) and accepting it, then answering prose anyway - which
                # is what Z.AI does, and the reason this fallback exists at all.
                # A timeout or a 5xx says nothing about the host's capabilities,
                # so it is raised for the retry loop instead of being read as an
                # answer about them.
                if is_transient(exc) and not is_malformed_answer(exc):
                    raise

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
        parsed = self._parse(response, response_model)
        # Only settled once the fallback has actually produced an object: one
        # garbled answer under a host that does enforce schemas would otherwise
        # give up strict validation for the rest of the process.
        if probing:
            self._supports_json_schema = False
        return parsed

    @staticmethod
    def _parse[T: BaseModel](response, response_model: type[T]) -> tuple[T, Usage]:
        choice = response.choices[0]
        usage = OpenAICompatibleChatBackend._usage(response)
        text = choice.message.content or ""

        if not text.strip():
            # Spell out what an empty 200 means here rather than letting
            # pydantic report "EOF while parsing a value", which names the
            # schema and not the cause.
            reasoning = getattr(choice.message, "reasoning_content", None) or ""
            spent_thinking = (
                f", {usage.output_tokens} output tokens of which {len(reasoning)} chars "
                "went to reasoning"
                if reasoning
                else f", {usage.output_tokens} output tokens"
            )
            raise EmptyCompletionError(
                f"{response_model.__name__}: model returned no content "
                f"(finish_reason={getattr(choice, 'finish_reason', None)!r}{spent_thinking})"
            )

        return response_model.model_validate_json(_json_object(text)), usage


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
        reason = _NO_EMBEDDING_MODEL_REASONS.get(provider, "has no default embedding model")
        raise ProviderConfigError(
            f"{provider} {reason}; set EMBEDDING_PROVIDER to one of "
            f"{', '.join(EMBEDDING_PROVIDERS)}, or name a model this host really serves "
            "with EMBEDDING_MODEL (plus EMBEDDING_BASE_URL if it lives elsewhere)"
        )
    return default


def resolve_base_url(provider: str, configured: str | None) -> str | None:
    """Return the API host: an explicit override, else the provider's own."""
    return configured or _BASE_URLS.get(provider)


def resolve_embedding_provider(settings: Settings) -> str:
    """Return the provider to embed with.

    Defaults to the chat provider so a single-vendor setup needs one setting,
    but falls back to Gemini when that vendor can't embed — which is how
    "Claude (or GLM) reviews, Gemini retrieves" works with nothing extra
    configured. An explicit ``EMBEDDING_PROVIDER`` still wins, including one
    that has no default model: that combination is an error naming the setting
    to fix, which is the point — a chat vendor that can't embed otherwise fails
    once per clause, deep inside a review, as a report of nothing but
    ``unknown``.
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
        model=resolved_model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout,
        # Only this family takes the parameter. Gemini is asked for a thinking
        # level per call, and Anthropic does no extended thinking unless
        # ``effort`` is passed, so neither needs telling to stop.
        disable_thinking=settings.llm_thinking == "disabled",
    )
