"""Grounding judge: verify citations/excerpts, optionally request retry."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import Agent
from app.schemas.clause import ClauseReview


@dataclass
class Verdict:
    """Judge outcome for a single review."""

    grounded: bool
    reason: str = ""
    should_retry: bool = False


class Judge(Agent[ClauseReview, Verdict]):
    """Checks that a review is grounded in its cited sources."""

    name = "judge"

    def run(self, payload: ClauseReview) -> Verdict:
        """Return a :class:`Verdict` for ``payload``.

        TODO: run guardrails (grounding, citation validity, no invented
        fallback); render ``prompts/judge.v1.jinja`` for the LLM check and set
        ``should_retry`` when the assessment is ungrounded.
        """
        raise NotImplementedError
