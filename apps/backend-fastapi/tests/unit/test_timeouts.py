"""Unit tests for the request/session timeouts.

These guard two things that fail silently rather than loudly: the unit
conversion on the Gemini timeout (the SDK wants milliseconds, our settings are
in seconds — a 1000x error still "works", just uselessly), and the ordering
between how long a report is kept and how long a session lasts.
"""

from __future__ import annotations

from datetime import UTC, datetime

from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token
from app.llm.client import LLMClient
from app.rag.embedder import GeminiEmbedder


class _FakeHttpOptions:
    def __init__(self, timeout: int | None = None) -> None:
        self.timeout = timeout


def _captured_client_timeout(monkeypatch, build) -> int:
    """Construct a Gemini-backed object and return the timeout it hands the SDK."""
    captured: dict[str, object] = {}

    class _FakeGenaiModule:
        @staticmethod
        def Client(**kwargs):  # noqa: N802 - mirrors google.genai.Client
            captured.update(kwargs)
            return object()

    import google.genai as real_genai

    monkeypatch.setattr(real_genai.types, "HttpOptions", _FakeHttpOptions)
    monkeypatch.setattr("google.genai.Client", _FakeGenaiModule.Client)

    build()._get_client()
    return captured["http_options"].timeout  # type: ignore[union-attr]


def test_llm_client_sends_timeout_to_sdk_in_milliseconds(monkeypatch) -> None:
    timeout_ms = _captured_client_timeout(
        monkeypatch, lambda: LLMClient(timeout_seconds=45)
    )
    assert timeout_ms == 45_000


def test_embedder_sends_timeout_to_sdk_in_milliseconds(monkeypatch) -> None:
    timeout_ms = _captured_client_timeout(
        monkeypatch, lambda: GeminiEmbedder(timeout_seconds=45)
    )
    assert timeout_ms == 45_000


def test_llm_timeout_defaults_to_configured_setting(monkeypatch) -> None:
    expected = get_settings().llm_timeout_seconds
    assert _captured_client_timeout(monkeypatch, LLMClient) == expected * 1000


def test_report_ttl_does_not_outlive_the_session() -> None:
    """A report must never expire later than the token that can still fetch it.

    Overriding a clause reloads the report by id, so a report that outlives
    the session is unreachable, and a session that outlives every report
    leaves users staring at 404s.
    """
    settings = get_settings()
    assert settings.retention_ttl_seconds < settings.access_token_expire_minutes * 60


def test_access_token_expires_after_the_configured_window() -> None:
    settings = get_settings()
    token = create_access_token(subject="user-1")

    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    lifetime_minutes = (
        datetime.fromtimestamp(claims["exp"], tz=UTC) - datetime.now(UTC)
    ).total_seconds() / 60

    # Allow a few seconds of slack for the time spent inside this test.
    assert settings.access_token_expire_minutes - 1 < lifetime_minutes
    assert lifetime_minutes <= settings.access_token_expire_minutes
