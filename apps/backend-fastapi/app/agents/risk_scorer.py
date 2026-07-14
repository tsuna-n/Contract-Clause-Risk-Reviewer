"""Risk scorer: risk level + rationale + citations."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import Agent
from app.schemas.clause import Clause, ClauseReview
from app.schemas.playbook import RetrievalHit


@dataclass
class RiskScorerInput:
    """Input bundle for the risk scorer."""

    clause: Clause
    hits: list[RetrievalHit]


class RiskScorer(Agent[RiskScorerInput, ClauseReview]):
    """Produces a grounded risk assessment for a clause."""

    name = "risk_scorer"

    def run(self, payload: RiskScorerInput) -> ClauseReview:
        """Assess ``payload.clause`` against the retrieved positions.

        TODO: render ``prompts/risk_scorer.v1.jinja`` with the hits and call
        ``parse_structured`` to produce a ClauseReview (risk_level, rationale,
        citations). Fallback text must match playbook wording verbatim.
        """
        raise NotImplementedError
