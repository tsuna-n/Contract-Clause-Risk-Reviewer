"""Clause type classifier (structured output)."""

from __future__ import annotations

from app.agents.base import Agent
from app.schemas.clause import Clause
from app.schemas.taxonomy import ClauseType


class Classifier(Agent[Clause, ClauseType]):
    """Assigns a :class:`ClauseType` to a clause."""

    name = "classifier"

    def run(self, payload: Clause) -> ClauseType:
        """Classify ``payload`` into a clause type.

        TODO: render ``prompts/classifier.v1.jinja`` and call
        ``llm.structured.parse_structured`` with a ClauseType response model.
        """
        raise NotImplementedError
