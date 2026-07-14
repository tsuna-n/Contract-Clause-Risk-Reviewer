"""Guardrail: attach the not-legal-advice disclaimer to every report."""

from __future__ import annotations

DISCLAIMER = (
    "This automated review is for informational purposes only and does not "
    "constitute legal advice. Consult qualified counsel before relying on it."
)


def disclaimer_text() -> str:
    """Return the standard disclaimer string."""
    return DISCLAIMER
