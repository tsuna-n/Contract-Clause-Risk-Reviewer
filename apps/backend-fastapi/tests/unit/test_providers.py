"""Unit tests for provider selection and the per-vendor adapters.

The promise these guard is "swap the vendor in ``.env``, change nothing else":
that only holds if every backend resolves its own model/key/host the same way
and returns the same ``(parsed model, Usage)`` shape from
``complete_structured``. Vendor SDKs are faked - these are about our mapping,
not about theirs.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.ai.llm import LLMClient
from app.ai.providers import (
    ANTHROPIC,
    GEMINI,
    OPENAI,
    ZAI,
    AnthropicChatBackend,
    EmptyCompletionError,
    GeminiChatBackend,
    OpenAICompatibleChatBackend,
    ProviderConfigError,
    Usage,
    _strict_json_schema,
    build_chat_backend,
    is_transient,
    resolve_api_key,
    resolve_base_url,
    resolve_chat_model,
    resolve_embedding_model,
    resolve_embedding_provider,
    resolve_provider,
)
from app.config import get_settings


class _Verdict(BaseModel):
    risk_level: str
    rationale: str


#: Every provider-related field, blanked. Tests start from this rather than
#: from the developer's own ``.env``, so they assert behaviour instead of
#: whichever vendor that file happens to select today.
_BLANK_PROVIDER_FIELDS = {
    "llm_provider": "gemini",
    "llm_model": None,
    "llm_api_key": None,
    "llm_base_url": None,
    "embedding_provider": None,
    "embedding_model": None,
    "embedding_api_key": None,
    "embedding_base_url": None,
}


def _settings(**overrides):
    """Base settings with every provider field blanked, then overridden."""
    return get_settings().model_copy(update={**_BLANK_PROVIDER_FIELDS, **overrides})


# --- resolution --------------------------------------------------------------


def test_provider_names_are_normalized_and_validated() -> None:
    assert resolve_provider("  Anthropic ", field="LLM_PROVIDER") == ANTHROPIC
    assert resolve_provider(None, field="LLM_PROVIDER") == GEMINI

    with pytest.raises(ProviderConfigError, match="unknown provider 'grok'"):
        resolve_provider("grok", field="LLM_PROVIDER")


def test_each_provider_has_a_default_model_except_openai() -> None:
    assert resolve_chat_model(GEMINI, None) == "gemini-3.5-flash"
    assert resolve_chat_model(ANTHROPIC, None) == "claude-opus-5"
    assert resolve_chat_model(ZAI, None) == "glm-4.6"
    # An explicit model always wins over the default.
    assert resolve_chat_model(ANTHROPIC, "claude-sonnet-5") == "claude-sonnet-5"

    # OpenAI's catalogue turns over too fast to guess at: say so instead of 404ing.
    with pytest.raises(ProviderConfigError, match="LLM_MODEL must be set"):
        resolve_chat_model(OPENAI, None)


def test_a_half_switched_env_is_rejected_by_name_rather_than_by_404() -> None:
    """The easy mistake: change LLM_PROVIDER, forget LLM_MODEL.

    The vendor's answer to that is a bare 404 that names neither setting, so
    the mismatch is caught here while both values are still in hand.
    """
    with pytest.raises(ProviderConfigError, match="gemini model but the provider is anthropic"):
        resolve_chat_model(ANTHROPIC, "gemini-3.5-flash")

    with pytest.raises(ProviderConfigError, match="EMBEDDING_MODEL"):
        resolve_embedding_model(ZAI, "gemini-embedding-001")

    # A GLM model over an OpenAI-compatible host is a real pairing, not a
    # mistake - both speak the same wire protocol, so it passes.
    assert resolve_chat_model(OPENAI, "glm-4.6") == "glm-4.6"
    # And an unrecognized name (self-hosted, fine-tuned) is nobody's business.
    assert resolve_chat_model(OPENAI, "my-finetune-v3") == "my-finetune-v3"


def test_zai_fills_in_its_own_host_and_an_override_still_wins() -> None:
    assert resolve_base_url(ZAI, None) == "https://api.z.ai/api/paas/v4"
    assert resolve_base_url(ZAI, "http://localhost:8080/v1") == "http://localhost:8080/v1"
    # Gemini and Anthropic talk to their own SDK defaults.
    assert resolve_base_url(GEMINI, None) is None


def test_api_key_falls_back_to_the_providers_own_env_var() -> None:
    settings = _settings(gemini_api_key="gem", anthropic_api_key="ant", zai_api_key="zai")

    assert resolve_api_key(settings, GEMINI, override=None) == "gem"
    assert resolve_api_key(settings, ANTHROPIC, override=None) == "ant"
    assert resolve_api_key(settings, ZAI, override=None) == "zai"
    # LLM_API_KEY overrides whichever provider is selected.
    assert resolve_api_key(settings, ANTHROPIC, override="explicit") == "explicit"


def test_embedding_provider_follows_chat_unless_that_vendor_cannot_embed() -> None:
    assert resolve_embedding_provider(_settings(llm_provider="zai")) == ZAI
    # Anthropic has no embedding API, so retrieval quietly stays on Gemini.
    assert resolve_embedding_provider(_settings(llm_provider="anthropic")) == GEMINI
    # An explicit setting wins over both.
    assert (
        resolve_embedding_provider(
            _settings(llm_provider="anthropic", embedding_provider="zai")
        )
        == ZAI
    )


def test_embedding_model_defaults_per_provider_and_rejects_anthropic() -> None:
    assert resolve_embedding_model(GEMINI, None) == "gemini-embedding-001"
    assert resolve_embedding_model(ZAI, None) == "embedding-3"

    with pytest.raises(ProviderConfigError, match="no embedding API"):
        resolve_embedding_model(ANTHROPIC, None)


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("gemini", None, GeminiChatBackend),
        ("anthropic", None, AnthropicChatBackend),
        ("zai", None, OpenAICompatibleChatBackend),
        ("openai", "gpt-5", OpenAICompatibleChatBackend),
    ],
)
def test_build_chat_backend_picks_the_right_adapter(provider, model, expected) -> None:
    backend = build_chat_backend(
        _settings(llm_provider=provider, llm_model=model, llm_api_key="k")
    )
    assert isinstance(backend, expected)


def test_a_blank_key_is_reported_at_startup_not_as_a_401_per_clause() -> None:
    """``ANTHROPIC_API_KEY=`` with nothing after it is a half-finished edit.

    Every SDK here accepts the empty string at construction and only fails
    later with a 401 on each call - which in this pipeline means a report
    where all 11 clauses came back ``unknown`` and nothing says why.
    """
    with pytest.raises(ProviderConfigError, match="ANTHROPIC_API_KEY is not set"):
        build_chat_backend(_settings(llm_provider="anthropic", anthropic_api_key="   "))

    # LLM_API_KEY satisfies whichever provider is selected.
    backend = build_chat_backend(
        _settings(llm_provider="anthropic", anthropic_api_key=None, llm_api_key="k")
    )
    assert isinstance(backend, AnthropicChatBackend)


# --- anthropic ---------------------------------------------------------------


class _FakeAnthropicUsage:
    input_tokens = 11
    output_tokens = 7
    cache_read_input_tokens = 3


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeAnthropicResponse:
    usage = _FakeAnthropicUsage()

    def __init__(self, parsed_output, text: str = "") -> None:
        self.parsed_output = parsed_output
        self.content = [_FakeTextBlock(text)] if text else []


class _FakeAnthropicMessages:
    """Records calls; optionally rejects ``output_config`` like Haiku does."""

    def __init__(self, response, *, reject_effort: bool = False) -> None:
        self._response = response
        self._reject_effort = reject_effort
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._reject_effort and "output_config" in kwargs:
            raise ValueError("output_config: effort is not supported on this model")
        return self._response


def _anthropic_backend(
    response, *, model: str = "claude-opus-5", reject_effort: bool = False
) -> tuple[AnthropicChatBackend, _FakeAnthropicMessages]:
    backend = AnthropicChatBackend(
        model=model, api_key="k", base_url=None, timeout_seconds=30
    )
    messages = _FakeAnthropicMessages(response, reject_effort=reject_effort)
    backend._client = type("_Client", (), {"messages": messages})()
    return backend, messages


def test_anthropic_structured_output_returns_the_parsed_model_and_usage() -> None:
    verdict = _Verdict(risk_level="high", rationale="uncapped liability")
    backend, messages = _anthropic_backend(_FakeAnthropicResponse(verdict))

    parsed, usage = backend.complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )

    assert parsed is verdict
    assert usage == Usage(input_tokens=11, output_tokens=7, cache_read_input_tokens=3)
    assert messages.calls[0]["output_format"] is _Verdict
    assert messages.calls[0]["system"] == "sys"


def test_anthropic_structured_output_revalidates_when_parsing_stopped_early() -> None:
    """``parsed_output`` is None on a truncated or refused turn.

    Re-validating the raw text turns that into a pydantic error naming the
    missing field, instead of an AttributeError on None three frames later.
    """
    raw = '{"risk_level": "low", "rationale": "capped at fees"}'
    backend, _ = _anthropic_backend(_FakeAnthropicResponse(None, text=raw))

    parsed, _ = backend.complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )
    assert parsed.risk_level == "low"


def test_anthropic_effort_is_only_sent_when_the_api_accepts_the_value() -> None:
    backend, messages = _anthropic_backend(_FakeAnthropicResponse(None, text="ok"))

    backend.complete(system="s", prompt="p", max_tokens=64, effort="high")
    assert messages.calls[-1]["output_config"] == {"effort": "high"}

    # An unknown level would 400 the whole request, so it's dropped instead.
    backend.complete(system="s", prompt="p", max_tokens=64, effort="thorough")
    assert "output_config" not in messages.calls[-1]


def test_anthropic_retries_without_effort_on_models_that_reject_it() -> None:
    """Haiku 4.5 and the 4.5-era Sonnet 400 on ``output_config``.

    Which models accept it moves with each release, so the answer is asked
    once and remembered rather than kept in a list that goes stale.
    """
    backend, messages = _anthropic_backend(
        _FakeAnthropicResponse(None, text="ok"), model="claude-haiku-4-5", reject_effort=True
    )

    text, _ = backend.complete(system="s", prompt="p", max_tokens=64, effort="high")
    assert text == "ok"
    assert ["output_config" in call for call in messages.calls] == [True, False]

    # Second call skips the probe entirely.
    backend.complete(system="s", prompt="p", max_tokens=64, effort="high")
    assert "output_config" not in messages.calls[-1]
    assert len(messages.calls) == 3


def test_anthropic_refusal_returns_empty_text_rather_than_raising() -> None:
    """A refusal is a 200 with no content blocks, not an exception."""
    backend, _ = _anthropic_backend(_FakeAnthropicResponse(None))

    text, usage = backend.complete(system="s", prompt="p", max_tokens=64, effort="high")
    assert text == ""
    assert usage.input_tokens == 11


# --- openai-compatible -------------------------------------------------------


class _FakeOpenAIUsage:
    prompt_tokens = 20
    completion_tokens = 5
    prompt_tokens_details = type("_Details", (), {"cached_tokens": 8})()


class _FakeChoice:
    def __init__(self, content: str, *, finish_reason: str = "stop", reasoning: str = "") -> None:
        self.finish_reason = finish_reason
        self.message = type(
            "_Message", (), {"content": content, "reasoning_content": reasoning}
        )()


class _FakeOpenAIResponse:
    usage = _FakeOpenAIUsage()

    def __init__(self, content: str, **choice: object) -> None:
        self.choices = [_FakeChoice(content, **choice)]  # type: ignore[arg-type]


class _BadRequest(Exception):
    """A 400 — how every one of these hosts answers a parameter it doesn't know."""

    status_code = 400


class _Timeout(Exception):
    """Stands in for ``openai.APITimeoutError``, matched by name."""


class _FakeCompletions:
    """Records calls; optionally rejects a parameter like a partial host does."""

    def __init__(
        self,
        content: str,
        *,
        reject_json_schema: bool = False,
        ignore_json_schema: bool = False,
        reject_thinking: bool = False,
        fail_first_with: Exception | None = None,
        **choice: object,
    ) -> None:
        self._content = content
        self._reject_json_schema = reject_json_schema
        self._ignore_json_schema = ignore_json_schema
        self._reject_thinking = reject_thinking
        self._fail_first_with = fail_first_with
        self._choice = choice
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail_first_with is not None and len(self.calls) == 1:
            raise self._fail_first_with
        fmt = kwargs.get("response_format") or {}
        if self._reject_json_schema and fmt.get("type") == "json_schema":
            raise ValueError("response_format.json_schema is not supported")
        if self._reject_thinking and "extra_body" in kwargs:
            raise _BadRequest("unknown parameter: thinking")
        if self._ignore_json_schema and fmt.get("type") == "json_schema":
            # Z.AI takes the parameter with a 200 and answers markdown anyway.
            return _FakeOpenAIResponse("**Risk Level:** High\n\nUncapped liability.")
        return _FakeOpenAIResponse(self._content, **self._choice)


def _openai_backend(completions, *, disable_thinking: bool = False) -> OpenAICompatibleChatBackend:
    backend = OpenAICompatibleChatBackend(
        model="glm-4.6",
        api_key="k",
        base_url="https://api.z.ai/api/paas/v4",
        timeout_seconds=30,
        disable_thinking=disable_thinking,
    )
    chat = type("_Chat", (), {"completions": completions})()
    backend._client = type("_Client", (), {"chat": chat})()
    return backend


def test_openai_structured_output_prefers_a_strict_json_schema() -> None:
    completions = _FakeCompletions('{"risk_level": "medium", "rationale": "net 60"}')
    backend = _openai_backend(completions)

    parsed, usage = backend.complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )

    assert parsed.risk_level == "medium"
    assert usage == Usage(input_tokens=20, output_tokens=5, cache_read_input_tokens=8)
    fmt = completions.calls[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


def test_openai_falls_back_to_json_mode_once_and_remembers_it() -> None:
    """Hosts that only implement ``json_object`` must still work.

    The probe is remembered so a 20-clause contract pays it once rather than
    twice per clause.
    """
    completions = _FakeCompletions(
        '{"risk_level": "high", "rationale": "no cap"}', reject_json_schema=True
    )
    backend = _openai_backend(completions)

    first, _ = backend.complete_structured(
        system="sys", prompt="a", response_model=_Verdict, max_tokens=512
    )
    second, _ = backend.complete_structured(
        system="sys", prompt="b", response_model=_Verdict, max_tokens=512
    )

    assert first.risk_level == "high" and second.risk_level == "high"
    kinds = [call["response_format"]["type"] for call in completions.calls]
    assert kinds == ["json_schema", "json_object", "json_object"]
    # The schema rides along in the system prompt when the host can't enforce it.
    assert "JSON Schema" in completions.calls[1]["messages"][0]["content"]


def test_a_host_that_takes_json_schema_and_ignores_it_still_falls_back() -> None:
    """Z.AI's actual behaviour: 200, ``json_schema`` accepted, markdown returned.

    Verified live against ``api.z.ai`` on 2026-07-30 — so "did the host reject
    the parameter" is the wrong question to gate the fallback on. What the
    reviewer sees if this path is missed is every clause ``unknown``.
    """
    completions = _FakeCompletions(
        '{"risk_level": "high", "rationale": "no cap"}', ignore_json_schema=True
    )
    backend = _openai_backend(completions)

    parsed, _ = backend.complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )

    assert parsed.risk_level == "high"
    assert [call["response_format"]["type"] for call in completions.calls] == [
        "json_schema",
        "json_object",
    ]


def test_one_garbled_answer_does_not_give_up_strict_validation_for_the_run() -> None:
    """The fallback is only remembered once it has produced an object.

    A host that does enforce schemas is entitled to the occasional bad turn,
    and the probe here outlives the request that triggered it.
    """
    completions = _FakeCompletions("not json at all")
    backend = _openai_backend(completions)

    for _ in range(2):
        with pytest.raises(ValidationError):
            backend.complete_structured(
                system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
            )

    assert [call["response_format"]["type"] for call in completions.calls] == [
        "json_schema",
        "json_object",
        "json_schema",
        "json_object",
    ]


def test_strict_schema_closes_objects_and_requires_every_property() -> None:
    schema = _strict_json_schema(_Verdict.model_json_schema())

    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["rationale", "risk_level"]


def test_json_mode_answers_wrapped_in_fences_or_prose_still_parse() -> None:
    """``json_object`` is a request, not a guarantee.

    Hosts without real schema enforcement wrap the object often enough that
    losing the clause over a code fence would be the wrong trade.
    """
    completions = _FakeCompletions(
        'Sure! ```json\n{"risk_level": "low", "rationale": "mutual"}\n```'
    )
    parsed, _ = _openai_backend(completions).complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )
    assert parsed.rationale == "mutual"


# --- reasoning budget --------------------------------------------------------
#
# The failure that cost the 2026-07-30 eval run three clauses: on a reasoning
# model the thinking tokens come out of the same `max_tokens` as the answer, so
# a long think returns a 200 with empty `content`.


def test_thinking_is_switched_off_when_configured() -> None:
    completions = _FakeCompletions('{"risk_level": "high", "rationale": "no cap"}')
    backend = _openai_backend(completions, disable_thinking=True)

    backend.complete_structured(
        system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
    )

    assert completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_a_host_that_rejects_thinking_is_asked_again_without_it_once() -> None:
    """``thinking`` is Z.AI's, not OpenAI's, so other hosts answer 400."""
    completions = _FakeCompletions(
        '{"risk_level": "low", "rationale": "capped"}', reject_thinking=True
    )
    backend = _openai_backend(completions, disable_thinking=True)

    first, _ = backend.complete_structured(
        system="sys", prompt="a", response_model=_Verdict, max_tokens=512
    )
    second, _ = backend.complete_structured(
        system="sys", prompt="b", response_model=_Verdict, max_tokens=512
    )

    assert first.risk_level == "low" and second.risk_level == "low"
    # Probed once and remembered: sent, rejected, retried without — then never
    # sent again.
    assert ["extra_body" in call for call in completions.calls] == [True, False, False]


def test_a_timeout_is_not_read_as_a_capability_the_host_lacks() -> None:
    """Both probes here are remembered for the life of the process, so reading a
    slow call as "unsupported" degrades the whole run: thinking back on is what
    caused the slow calls, and JSON mode is the weaker of the two output modes.
    The timeout is raised for the retry loop to handle instead."""
    completions = _FakeCompletions(
        '{"risk_level": "low", "rationale": "capped"}', fail_first_with=_Timeout("timed out")
    )
    backend = _openai_backend(completions, disable_thinking=True)

    with pytest.raises(_Timeout):
        backend.complete_structured(
            system="sys", prompt="a", response_model=_Verdict, max_tokens=512
        )

    backend.complete_structured(system="sys", prompt="b", response_model=_Verdict, max_tokens=512)
    assert all("extra_body" in call for call in completions.calls)
    assert all(call["response_format"]["type"] == "json_schema" for call in completions.calls)


def test_an_empty_answer_names_the_budget_it_spent_not_the_schema() -> None:
    """Pydantic's answer to "" is "EOF while parsing a value", which sends the
    reader to the schema instead of to the reason."""
    completions = _FakeCompletions("", finish_reason="length", reasoning="x" * 4556)
    backend = _openai_backend(completions)

    with pytest.raises(EmptyCompletionError, match="reasoning"):
        backend.complete_structured(
            system="sys", prompt="clause", response_model=_Verdict, max_tokens=512
        )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("APITimeoutError", True),
        ("APIConnectionError", True),
        ("RateLimitError", True),
        ("InternalServerError", True),
        ("ServerError", True),  # google.genai
        ("ResourceExhausted", True),  # gemini's 429
        ("OverloadedError", True),  # anthropic's 529
        ("AuthenticationError", False),
        ("BadRequestError", False),
        ("NotFoundError", False),
    ],
)
def test_transient_failures_are_recognized_across_vendors_by_name(name, expected) -> None:
    """Matched by name so the retry loop doesn't import three SDKs to catch
    three spellings of "the network was busy"."""
    assert is_transient(type(name, (Exception,), {})()) is expected


def test_a_status_code_is_believed_over_the_class_name() -> None:
    assert is_transient(_BadRequest()) is False
    assert is_transient(type("_Weird", (Exception,), {"status_code": 503})()) is True


# --- client facade -----------------------------------------------------------


def test_llm_client_accumulates_usage_across_calls() -> None:
    verdict = _Verdict(risk_level="low", rationale="mutual")
    backend, _ = _anthropic_backend(_FakeAnthropicResponse(verdict))
    client = LLMClient(backend=backend)

    client.complete_structured(
        system="s", prompt="p", response_model=_Verdict, max_tokens=64
    )
    client.complete_structured(
        system="s", prompt="p", response_model=_Verdict, max_tokens=64
    )

    assert client.usage == Usage(input_tokens=22, output_tokens=14, cache_read_input_tokens=6)
    assert client.model == "claude-opus-5"


# --- retries -----------------------------------------------------------------


class _ScriptedBackend:
    """Plays one scripted outcome per attempt, then repeats the last one.

    An outcome is either a value to return or an exception to raise, which is
    what makes "fails once, then works" expressible.
    """

    model = "scripted"

    def __init__(self, *outcomes: object) -> None:
        self._outcomes = outcomes
        self.attempts = 0

    def complete_structured(self, **_kwargs):
        self.attempts += 1
        outcome = self._outcomes[min(self.attempts, len(self._outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, Usage(input_tokens=3, output_tokens=1)


def _retrying_client(monkeypatch, backend, **overrides) -> LLMClient:
    """An ``LLMClient`` with retry settings pinned, and no real backoff sleep."""
    settings = get_settings().model_copy(
        update={
            "llm_max_attempts": 3,
            "llm_retry_backoff_seconds": 0.0,
            "llm_timeout_seconds": 120,
            **overrides,
        }
    )
    monkeypatch.setattr("app.ai.llm.get_settings", lambda: settings)
    return LLMClient(backend=backend)


def test_an_empty_answer_is_asked_again_rather_than_costing_the_clause(monkeypatch) -> None:
    verdict = _Verdict(risk_level="high", rationale="uncapped")
    backend = _ScriptedBackend(EmptyCompletionError("no content"), verdict)
    client = _retrying_client(monkeypatch, backend)

    parsed = client.complete_structured(system="s", prompt="p", response_model=_Verdict)

    assert parsed is verdict
    assert backend.attempts == 2
    # Only the attempt that produced an answer is billed to the report.
    assert client.usage == Usage(input_tokens=3, output_tokens=1)


def test_a_bad_request_is_not_retried(monkeypatch) -> None:
    """A 400 and a rejected key answer the same way however often they're asked;
    retrying only delays the message that says so."""
    backend = _ScriptedBackend(_BadRequest("max_tokens is invalid"))
    client = _retrying_client(monkeypatch, backend)

    with pytest.raises(_BadRequest):
        client.complete_structured(system="s", prompt="p", response_model=_Verdict)
    assert backend.attempts == 1


def test_retries_stop_at_the_configured_attempt_count(monkeypatch) -> None:
    backend = _ScriptedBackend(EmptyCompletionError("no content"))
    client = _retrying_client(monkeypatch, backend, llm_max_attempts=2)

    with pytest.raises(EmptyCompletionError):
        client.complete_structured(system="s", prompt="p", response_model=_Verdict)
    assert backend.attempts == 2


def test_a_call_that_already_spent_the_time_budget_is_not_repeated(monkeypatch) -> None:
    """A timeout has already burned the per-call ceiling. Asking twice more
    would put one clause of ~40 past six minutes on its own, so the retry
    budget is wall clock as well as attempts."""
    backend = _ScriptedBackend(_Timeout("timed out"))
    client = _retrying_client(monkeypatch, backend, llm_timeout_seconds=0)

    with pytest.raises(_Timeout):
        client.complete_structured(system="s", prompt="p", response_model=_Verdict)
    assert backend.attempts == 1
