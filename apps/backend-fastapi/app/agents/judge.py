"""Grounding judge: verify citations/excerpts, optionally request retry."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app.agents.base import Agent
from app.core.config import get_settings
from app.guardrails.citation_validity import invalid_citations
from app.guardrails.grounding import is_grounded
from app.guardrails.no_invented_fallback import is_allowed_fallback
from app.llm.client import LLMClient
from app.llm.structured import parse_structured
from app.prompts import render
from app.schemas.clause import ClauseReview
from app.schemas.playbook import PlaybookPosition

_SYSTEM_PROMPT = "You are a strict grounding verification judge."


@dataclass
class Verdict:
    """Judge outcome for a single review."""

    grounded: bool
    reason: str = ""
    should_retry: bool = False


class _LLMVerdict(BaseModel):
    grounded: bool
    reason: str = ""


class Judge(Agent[ClauseReview, Verdict]):
    """Checks that a review is grounded in its cited sources."""

    name = "judge"

    def __init__(self, llm: LLMClient, known_positions: dict[str, PlaybookPosition]) -> None:
        super().__init__(llm)
        self.known_positions = known_positions

    def run(self, payload: ClauseReview) -> Verdict:
        """Return a :class:`Verdict` for ``payload``.

        Runs the deterministic guardrails (citation validity, excerpt
        grounding, no-invented-fallback) first; only calls the LLM judge for
        the softer "rationale doesn't overreach" check once those pass.
        """
        known_ids = set(self.known_positions)

        unknown = invalid_citations(payload, known_ids)
        if unknown:
            return Verdict(
                grounded=False,
                reason=f"citation(s) reference unknown playbook position(s): {unknown}",
                should_retry=True,
            )

        for citation in payload.citations:
            position = self.known_positions[citation.playbook_position_id]
            source_text = f"{position.preferred_language} {position.fallback_language}"
            if not is_grounded(citation.excerpt, source_text):
                return Verdict(
                    grounded=False,
                    reason=f"excerpt for citation {citation.citation_id} not grounded",
                    should_retry=True,
                )

        if not is_allowed_fallback(payload.suggested_fallback, list(self.known_positions.values())):
            return Verdict(
                grounded=False,
                reason="suggested fallback does not match playbook wording verbatim",
                should_retry=True,
            )

        if not get_settings().enable_judge:
            return Verdict(grounded=True, reason="deterministic checks passed")

        prompt = render("judge.v1.jinja", clause_text=payload.clause.text, review=payload)
        llm_verdict = parse_structured(
            self.llm,
            system=_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=_LLMVerdict,
        )
        return Verdict(
            grounded=llm_verdict.grounded,
            reason=llm_verdict.reason or "deterministic checks passed",
            should_retry=not llm_verdict.grounded,
        )
