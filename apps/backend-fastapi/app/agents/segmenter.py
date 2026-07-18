"""Clause segmentation: regex numbering first, paragraph fallback."""

from __future__ import annotations

from app.agents.base import Agent
from app.parsers.models import ParsedDocument
from app.parsers.normalizer import is_heading
from app.schemas.clause import Clause, Span


class Segmenter(Agent[ParsedDocument, list[Clause]]):
    """Splits a parsed document into individual clauses."""

    name = "segmenter"

    def run(self, payload: ParsedDocument) -> list[Clause]:
        """Return the clauses found in ``payload``.

        Splits on numbered headings (see ``normalizer.is_heading``). Documents
        with no detectable headings fall back to a blank-line paragraph split;
        an LLM-guessed split would risk spans that don't actually exist in the
        source text, which the grounding guardrail would then reject anyway.
        """
        boundaries = self._heading_boundaries(payload.text)
        if not boundaries:
            return self._paragraph_fallback(payload)
        return self._clauses_from_boundaries(payload, boundaries)

    @staticmethod
    def _heading_boundaries(text: str) -> list[tuple[int, str]]:
        boundaries: list[tuple[int, str]] = []
        offset = 0
        for line in text.split("\n"):
            if is_heading(line):
                boundaries.append((offset, line.strip()))
            offset += len(line) + 1
        return boundaries

    @staticmethod
    def _clauses_from_boundaries(
        payload: ParsedDocument, boundaries: list[tuple[int, str]]
    ) -> list[Clause]:
        clauses: list[Clause] = []
        for idx, (start, heading) in enumerate(boundaries):
            end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(payload.text)
            text = payload.text[start:end].strip()
            if not text:
                continue
            clauses.append(
                Clause(
                    id=f"clause-{idx + 1}",
                    text=text,
                    span=Span(start=start, end=end, page=payload.page_for_offset(start)),
                    heading=heading,
                )
            )
        return clauses

    @staticmethod
    def _paragraph_fallback(payload: ParsedDocument) -> list[Clause]:
        clauses: list[Clause] = []
        offset = 0
        for idx, paragraph in enumerate(payload.text.split("\n\n")):
            start = offset
            end = start + len(paragraph)
            offset = end + 2
            stripped = paragraph.strip()
            if not stripped:
                continue
            clauses.append(
                Clause(
                    id=f"clause-{idx + 1}",
                    text=stripped,
                    span=Span(start=start, end=end, page=payload.page_for_offset(start)),
                )
            )
        return clauses
