"""Guardrails — the deterministic checks that keep the model honest.

Each function answers one question about a generated review: does the quoted
excerpt really exist in the playbook, does every citation point at a real
position, and is the suggested fallback verbatim playbook wording rather than
something invented? :class:`~app.ai.agents.Judge` runs all of them before it
spends a call on the softer LLM check.
"""

from __future__ import annotations

from app.errors import GroundingError
from app.schemas import ClauseReview, PlaybookPosition

DISCLAIMER = (
    "This automated review is for informational purposes only and does not "
    "constitute legal advice. Consult qualified counsel before relying on it."
)


def disclaimer_text() -> str:
    """Return the standard not-legal-advice disclaimer attached to every report."""
    return DISCLAIMER


# --- grounding ---------------------------------------------------------------


def normalize_for_match(text: str) -> str:
    """Lightweight normalization used for substring grounding checks."""
    return " ".join(text.split()).lower()


def is_grounded(excerpt: str, source_text: str) -> bool:
    """Return ``True`` if ``excerpt`` appears (normalized) in ``source_text``."""
    return normalize_for_match(excerpt) in normalize_for_match(source_text)


def assert_grounded(excerpt: str, source_text: str) -> None:
    """Raise :class:`GroundingError` if ``excerpt`` is not grounded."""
    if not is_grounded(excerpt, source_text):
        raise GroundingError("excerpt not found in source text")


# --- citation validity -------------------------------------------------------


def invalid_citations(review: ClauseReview, known_position_ids: set[str]) -> list[str]:
    """Return citation ids that reference unknown positions."""
    return [
        c.citation_id for c in review.citations if c.playbook_position_id not in known_position_ids
    ]


def all_citations_valid(review: ClauseReview, known_position_ids: set[str]) -> bool:
    """Return ``True`` if every citation points at a known position."""
    return not invalid_citations(review, known_position_ids)


# --- no invented fallback ----------------------------------------------------


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
