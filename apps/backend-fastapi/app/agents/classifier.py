"""Clause type classifier (structured output)."""

from __future__ import annotations

from pydantic import BaseModel

from app.agents.base import Agent
from app.llm.structured import parse_structured
from app.prompts import render
from app.schemas.clause import Clause
from app.schemas.taxonomy import ClauseType

_SYSTEM_PROMPT = "You are a precise contract-clause classifier."


class _ClassificationResult(BaseModel):
    clause_type: ClauseType


class Classifier(Agent[Clause, ClauseType]):
    """Assigns a :class:`ClauseType` to a clause."""

    name = "classifier"

    def run(self, payload: Clause) -> ClauseType:
        """Classify ``payload`` into a clause type."""
        prompt = render(
            "classifier.v1.jinja",
            clause_types=[t.value for t in ClauseType],
            clause_text=payload.text,
        )
        result = parse_structured(
            self.llm,
            system=_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=_ClassificationResult,
        )
        return result.clause_type
