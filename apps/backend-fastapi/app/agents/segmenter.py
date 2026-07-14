"""Clause segmentation: regex numbering first, LLM fallback."""

from __future__ import annotations

from app.agents.base import Agent
from app.parsers.models import ParsedDocument
from app.schemas.clause import Clause


class Segmenter(Agent[ParsedDocument, list[Clause]]):
    """Splits a parsed document into individual clauses."""

    name = "segmenter"

    def run(self, payload: ParsedDocument) -> list[Clause]:
        """Return the clauses found in ``payload``.

        TODO: rule-based split on numbered headings (see
        ``normalizer.is_heading``); fall back to the LLM for messy documents.
        Populate each Clause span/page from the ParsedDocument offsets.
        """
        raise NotImplementedError
