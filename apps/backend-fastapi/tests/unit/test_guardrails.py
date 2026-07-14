"""Unit tests for guardrails."""

import pytest

from app.core.exceptions import GroundingError
from app.guardrails.grounding import assert_grounded, is_grounded
from app.guardrails.no_invented_fallback import is_allowed_fallback
from app.schemas.playbook import PlaybookPosition
from app.schemas.taxonomy import ClauseType


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
