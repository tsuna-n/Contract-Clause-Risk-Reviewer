"""Grounding guardrail: cited excerpts must exist in the source text."""

from __future__ import annotations

from app.core.exceptions import GroundingError


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
