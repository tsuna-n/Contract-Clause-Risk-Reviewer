"""The pipeline steps, one class each, in the order they run.

segment -> classify -> match -> score -> judge

:class:`MetadataExtractor` sits outside that chain: it runs once over the whole
document rather than once per clause, and nothing downstream depends on it.

Every agent takes one unit of work and returns one result, so
:class:`~app.ai.pipeline.Orchestrator` can compose them without knowing how any
of them is implemented. ``prompt_version`` is declared per agent so a run can be
attributed to the exact prompt template that produced it.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.ai.guardrails import (
    MIN_CITATION_EXCERPT_WORDS,
    invalid_citations,
    is_allowed_fallback,
    is_grounded,
)
from app.ai.llm import LLMClient, render_prompt
from app.ai.retrieval import Retriever, make_citation
from app.config import get_settings
from app.parsers import ParsedDocument, is_heading
from app.schemas import (
    Clause,
    ClauseReview,
    ClauseType,
    ContractMetadata,
    PlaybookPosition,
    RetrievalHit,
    RiskLevel,
    Span,
)


class Agent[InputT, OutputT](ABC):
    """Base class for pipeline agents."""

    name: str = "agent"
    prompt_version: str = "v1"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    def run(self, payload: InputT) -> OutputT:
        """Execute the agent for a single unit of work."""
        raise NotImplementedError


# --- 1. segment --------------------------------------------------------------


class Segmenter(Agent[ParsedDocument, list[Clause]]):
    """Splits a parsed document into individual clauses."""

    name = "segmenter"

    def run(self, payload: ParsedDocument) -> list[Clause]:
        """Return the clauses found in ``payload``.

        Splits on numbered headings (see ``parsers.is_heading``). Documents with
        no detectable headings fall back to a blank-line paragraph split; an
        LLM-guessed split would risk spans that don't actually exist in the
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


# --- 1b. contract metadata ----------------------------------------------------

_METADATA_SYSTEM_PROMPT = "You are a precise contract metadata extractor."
# How much of the document the extractor is shown. Parties and dates live in
# the preamble; the term and governing law live at the very end. Everything
# between is clause text this step has no use for, and sending it would pay
# for the whole contract on a call that reads two paragraphs of it.
#
# Kept deliberately tight: measured against a real CUAD contract, a ~9k-char
# excerpt took 113s on GLM-4.6 — close enough to the 120s per-call ceiling
# (``LLM_TIMEOUT_SECONDS``) that a slightly longer preamble would have lost the
# metadata to a timeout. These bounds still clear the first two pages and the
# signature block, which is where every one of these facts is written.
_METADATA_HEAD_CHARS = 4000
_METADATA_TAIL_CHARS = 2500


def _metadata_excerpt(text: str) -> str:
    """Return the document's opening and closing, joined by an elision marker."""
    if len(text) <= _METADATA_HEAD_CHARS + _METADATA_TAIL_CHARS:
        return text
    return (
        f"{text[:_METADATA_HEAD_CHARS]}\n\n[... middle of the document omitted ...]\n\n"
        f"{text[-_METADATA_TAIL_CHARS:]}"
    )


class MetadataExtractor(Agent[ParsedDocument, ContractMetadata]):
    """Reads the parties, dates, value and governing law off a contract.

    Runs once per document rather than once per clause: these are properties
    of the agreement, and they are stated in two places every contract has —
    the preamble and the closing.
    """

    name = "metadata_extractor"

    def run(self, payload: ParsedDocument) -> ContractMetadata:
        """Extract contract-level metadata, keeping only what the document says.

        The model is told to quote verbatim, and then every value it returns is
        checked against the document text before it is kept. Metadata is the
        part of the report a reviewer is least likely to double-check — it
        reads like it was transcribed, not inferred — so an invented party or
        a hallucinated contract value is dropped rather than displayed.
        """
        prompt = render_prompt(
            "metadata.v1.jinja", document_excerpt=_metadata_excerpt(payload.text)
        )
        extracted = self.llm.complete_structured(
            system=_METADATA_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=ContractMetadata,
        )
        return self._drop_ungrounded(extracted, payload.text)

    @staticmethod
    def _drop_ungrounded(metadata: ContractMetadata, source_text: str) -> ContractMetadata:
        """Blank out any value that isn't in ``source_text`` word-for-word."""

        def keep(value: str | None) -> str | None:
            cleaned = value.strip() if value else ""
            return cleaned if cleaned and is_grounded(cleaned, source_text) else None

        return ContractMetadata(
            parties=[p.strip() for p in metadata.parties if keep(p)],
            agreement_date=keep(metadata.agreement_date),
            effective_date=keep(metadata.effective_date),
            expiration_date=keep(metadata.expiration_date),
            contract_value=keep(metadata.contract_value),
            governing_law=keep(metadata.governing_law),
        )


# --- 2. classify -------------------------------------------------------------

_CLASSIFIER_SYSTEM_PROMPT = "You are a precise contract-clause classifier."


class _ClassificationResult(BaseModel):
    clause_type: ClauseType


class Classifier(Agent[Clause, ClauseType]):
    """Assigns a :class:`ClauseType` to a clause."""

    name = "classifier"

    def run(self, payload: Clause) -> ClauseType:
        """Classify ``payload`` into a clause type."""
        prompt = render_prompt(
            "classifier.v1.jinja",
            clause_types=[t.value for t in ClauseType],
            clause_text=payload.text,
        )
        result = self.llm.complete_structured(
            system=_CLASSIFIER_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=_ClassificationResult,
        )
        return result.clause_type


# --- 3. match ----------------------------------------------------------------


class Matcher(Agent[Clause, list[RetrievalHit]]):
    """Maps a clause to candidate playbook positions via the retriever."""

    name = "matcher"

    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        super().__init__(llm)
        self.retriever = retriever

    def run(self, payload: Clause) -> list[RetrievalHit]:
        """Return playbook positions matching ``payload``."""
        return self.retriever.retrieve(payload)

    def prewarm(self, clauses: list[Clause]) -> None:
        """Embed every clause in one request before the per-clause work starts."""
        self.retriever.prewarm(clauses)


# --- 4. score ----------------------------------------------------------------

_SCORER_SYSTEM_PROMPT = "You are a meticulous, grounded contract risk reviewer."
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
    #: Why the previous attempt at this clause was rejected, if there was one.
    #: Set by the orchestrator's one retry so the second attempt is told what
    #: was wrong - re-sending the identical prompt mostly bought the identical
    #: answer at twice the token cost.
    feedback: str | None = None


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
        prompt = render_prompt(
            "risk_scorer.v1.jinja",
            clause_type=payload.clause.clause_type.value,
            clause_text=payload.clause.text,
            hits=[
                {"citation_id": hit.position.id, "position": hit.position} for hit in payload.hits
            ],
            feedback=payload.feedback,
        )
        assessment = self.llm.complete_structured(
            system=_SCORER_SYSTEM_PROMPT,
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


# --- 5. judge ----------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = "You are a strict grounding verification judge."


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

    def __init__(
        self,
        llm: LLMClient,
        known_positions: dict[str, PlaybookPosition] | Callable[[], dict[str, PlaybookPosition]],
    ) -> None:
        super().__init__(llm)
        # A callable, not a dict, when the playbook can change under us. The
        # matcher retrieves from the live store, which the CRUD endpoints
        # write to; a snapshot taken at startup would call every position
        # added since then "unknown" and reject a perfectly good citation.
        # A plain dict is still accepted - tests pass a fixed one.
        self._positions = known_positions if callable(known_positions) else lambda: known_positions

    def run(self, payload: ClauseReview) -> Verdict:
        """Return a :class:`Verdict` for ``payload``.

        Runs the deterministic guardrails (citation validity, excerpt
        grounding, no-invented-fallback) first; only calls the LLM judge for
        the softer "rationale doesn't overreach" check once those pass.
        """
        # Resolved once per verdict: the three checks below must agree on one
        # view of the playbook, and re-reading it between them would also mean
        # three round trips to the store.
        known_positions = self._positions()
        known_ids = set(known_positions)

        unknown = invalid_citations(payload, known_ids)
        if unknown:
            return Verdict(
                grounded=False,
                reason=f"citation(s) reference unknown playbook position(s): {unknown}",
                should_retry=True,
            )

        for citation in payload.citations:
            position = known_positions[citation.playbook_position_id]
            source_text = f"{position.preferred_language} {position.fallback_language}"
            if not is_grounded(
                citation.excerpt, source_text, min_words=MIN_CITATION_EXCERPT_WORDS
            ):
                return Verdict(
                    grounded=False,
                    reason=(
                        f"excerpt for citation {citation.citation_id} is not a verbatim quote of "
                        f"at least {MIN_CITATION_EXCERPT_WORDS} words from that playbook position"
                    ),
                    should_retry=True,
                )

        if not is_allowed_fallback(payload.suggested_fallback, list(known_positions.values())):
            return Verdict(
                grounded=False,
                reason="suggested fallback does not match playbook wording verbatim",
                should_retry=True,
            )

        if not get_settings().enable_judge:
            return Verdict(grounded=True, reason="deterministic checks passed")

        prompt = render_prompt("judge.v1.jinja", clause_text=payload.clause.text, review=payload)
        llm_verdict = self.llm.complete_structured(
            system=_JUDGE_SYSTEM_PROMPT,
            prompt=prompt,
            response_model=_LLMVerdict,
        )
        return Verdict(
            grounded=llm_verdict.grounded,
            reason=llm_verdict.reason or "deterministic checks passed",
            should_retry=not llm_verdict.grounded,
        )
