"""Guardrail: every citation must reference a real playbook position."""

from __future__ import annotations

from app.schemas.clause import ClauseReview


def invalid_citations(review: ClauseReview, known_position_ids: set[str]) -> list[str]:
    """Return citation ids that reference unknown positions."""
    return [
        c.citation_id
        for c in review.citations
        if c.playbook_position_id not in known_position_ids
    ]


def all_citations_valid(review: ClauseReview, known_position_ids: set[str]) -> bool:
    """Return ``True`` if every citation points at a known position."""
    return not invalid_citations(review, known_position_ids)
