"""Unit tests for guardrails."""

import pytest

from app.ai.guardrails import assert_grounded, is_allowed_fallback, is_grounded
from app.errors import GroundingError
from app.schemas import ClauseType, PlaybookPosition


def _position() -> PlaybookPosition:
    return PlaybookPosition(
        id="p1",
        clause_type=ClauseType.TERMINATION,
        title="t",
        preferred_language="preferred",
        fallback_language="the exact fallback wording",
    )


def test_is_grounded_ignores_whitespace() -> None:
    assert is_grounded("hello   world", "say HELLO WORLD please")


def test_assert_grounded_raises() -> None:
    with pytest.raises(GroundingError):
        assert_grounded("not present", "some other text")


def test_allowed_fallback_verbatim() -> None:
    positions = [_position()]
    assert is_allowed_fallback("the exact fallback wording", positions)
    assert is_allowed_fallback(None, positions)


def test_invented_fallback_rejected() -> None:
    assert not is_allowed_fallback("some invented wording", [_position()])
