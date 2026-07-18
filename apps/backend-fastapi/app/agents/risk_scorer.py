"""Risk scorer: risk level + rationale + citations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.base import Agent
from app.llm.structured import parse_structured
from app.prompts import render
from app.rag.citation import make_citation
from app.schemas.clause import Clause, ClauseReview
from app.schemas.playbook import RetrievalHit
from app.schemas.taxonomy import RiskLevel

_SYSTEM_PROMPT = "You are a meticulous, grounded contract risk reviewer."
_LABEL_PREFIX_RE = re.compile(r"^\s*(preferred|fallback)\s*:\s*", re.IGNORECASE)
_WRAPPING_QUOTES = "\"'“”‘’"


def _clean_excerpt(text: str) -> str:
    """Strip a stray "Preferred:"/"Fallback:" label and wrapping quotes the model may echo back."""
    return _LABEL_PREFIX_RE.sub("", text).strip().strip(_WRAPPING_QUOTES).strip()


@dataclass
class RiskScorerInput:
    """Input bundle for the risk scorer."""

    clause: Clause
    hits: list[RetrievalHit]


class _CitedPoint(BaseModel):
    playbook_position_id: str
    excerpt: str


class _RiskAssessment(BaseModel):
    risk_level: RiskLevel
    rationale: str
    citations: list[_CitedPoint] = Field(default_factory=list)
    suggested_fallback: str | None = None


class RiskScorer(Agent[RiskScorerInput, ClauseReview]):
    """Produces a grounded risk assessment for a clause."""

    name = "risk_scorer"

    def run(self, payload: RiskScorerInput) -> ClauseReview:
        """Assess ``payload.clause`` against the retrieved positions.

        The LLM cites positions by their id and quotes an excerpt; grounding
        of that excerpt (and of any suggested fallback) is verified downstream
        by the judge, not here.
        """
        if not payload.hits:
            return ClauseReview(
                clause=payload.clause,
                risk_level=RiskLevel.UNKNOWN,
                rationale="No matching playbook position was retrieved for this clause.",
            )

        hits_by_id = {hit.position.id: hit for hit in payload.hits}
        prompt = render(
            "risk_scorer.v1.jinja",
            clause_type=payload.clause.clause_type.value,
            clause_text=payload.clause.text,
            hits=[
                {"citation_id": hit.position.id, "position": hit.position} for hit in payload.hits
            ],
        )
        assessment = parse_structured(
            self.llm,
            system=_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=_RiskAssessment,
        )

        citations = [
            make_citation(hits_by_id[c.playbook_position_id], _clean_excerpt(c.excerpt))
            for c in assessment.citations
            if c.playbook_position_id in hits_by_id
        ]
        suggested_fallback = (
            _clean_excerpt(assessment.suggested_fallback) if assessment.suggested_fallback else None
        )

        return ClauseReview(
            clause=payload.clause,
            risk_level=assessment.risk_level,
            rationale=assessment.rationale,
            citations=citations,
            suggested_fallback=suggested_fallback,
        )
