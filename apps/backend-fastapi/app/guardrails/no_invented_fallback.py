"""Guardrail: suggested fallback must match playbook text verbatim."""

from __future__ import annotations

from app.schemas.playbook import PlaybookPosition


def matches_verbatim(suggested: str, position: PlaybookPosition) -> bool:
    """Return ``True`` if ``suggested`` equals the position's fallback text.

    Comparison ignores leading/trailing whitespace only; the wording itself
    must match exactly so the model cannot invent fallback language.
    """
    return suggested.strip() == position.fallback_language.strip()


def is_allowed_fallback(suggested: str | None, positions: list[PlaybookPosition]) -> bool:
    """Return ``True`` if ``suggested`` is empty or matches some position."""
    if not suggested:
        return True
    return any(matches_verbatim(suggested, p) for p in positions)
