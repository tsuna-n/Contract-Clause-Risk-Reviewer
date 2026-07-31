"""The one test path that actually calls the model vendor.

Every other test in this suite mocks at the provider boundary, which makes
them fast and free and blind to exactly one class of bug: the vendor accepting
a request and answering something the pipeline can't use. The real example
this file exists for is Z.AI, which does not reject ``response_format:
json_schema`` - it accepts it and replies with markdown-fenced prose. A mocked
backend returns whatever the test told it to, so that failure reaches
production with a green suite behind it.

Not part of the default run: ``pyproject.toml`` deselects ``live_llm``, so
``pytest`` stays free and offline. Run it deliberately, against a ``.env``
with a real key:

    .venv/bin/python -m pytest -m live_llm

Costs roughly a dozen provider calls and a couple of minutes, and it needs
Postgres up with the playbook ingested (``python -m scripts.ingest_playbook``)
because the retriever and the judge both read positions from it.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from app.ai.guardrails import (
    MIN_CITATION_EXCERPT_WORDS,
    invalid_citations,
    is_allowed_fallback,
    is_grounded,
)
from app.ai.llm import LLMClient
from app.ai.pipeline import Orchestrator
from app.parsers import ParsedDocument
from app.schemas import ContractReviewReport, PlaybookPosition, RiskLevel

pytestmark = pytest.mark.live_llm

# The pipeline writes this rationale when a clause raised - a provider that
# times out, refuses, or answers unparseably lands here. Asserting on it is
# how a live run tells "the model judged this clause unknown" (a real answer)
# apart from "the call never produced one" (the thing under test).
_FAILURE_RATIONALE = "Automated review failed for this clause"


class _Answer(BaseModel):
    """A deliberately small schema - the point is the shape, not the content."""

    verdict: str = Field(description="exactly one of: yes, no")
    confidence: int = Field(ge=0, le=100)


def test_structured_output_returns_data_not_prose() -> None:
    """The provider must honour schema-constrained output, not just accept it.

    The cheapest possible check on the contract every agent depends on: if
    this fails, ``complete_structured`` is returning markdown and every clause
    in a review will fail one at a time, slowly and expensively.
    """
    client = LLMClient()

    answer = client.complete_structured(
        system="You answer strictly in the requested schema.",
        prompt="Is a contract clause requiring unlimited liability risky? Answer yes or no.",
        response_model=_Answer,
        max_tokens=256,
    )

    assert answer.verdict.strip().lower() in {"yes", "no"}
    assert 0 <= answer.confidence <= 100


@pytest.fixture(scope="module")
def live_report(
    orchestrator: Orchestrator,
    sample_document: ParsedDocument,
) -> ContractReviewReport:
    """One real review of the three-clause NDA, shared by the assertions below.

    Module-scoped because it is the expensive part - minutes of provider time
    and the only thing in this file that costs real money. The assertions that
    follow are separate tests so a failure names which property broke, but
    they all read this single run.
    """
    return orchestrator.review(
        sample_document,
        contract_id="live-nda",
        session_id="live-test",
    )


def test_every_clause_gets_a_real_answer(live_report: ContractReviewReport) -> None:
    """No clause may fall back to the failure rationale.

    This is the assertion the whole file is for. Six of eight clauses failed
    this way before ``LLM_THINKING=disabled``, and no mocked test could have
    caught it: the mock answered instantly and correctly every time.
    """
    assert live_report.reviews, "segmentation produced no clauses to review"

    failed = [
        review.clause.id for review in live_report.reviews if _FAILURE_RATIONALE in review.rationale
    ]
    assert not failed, f"provider failed to answer for clause(s): {failed}"


def test_the_thai_nda_segments_into_its_three_clauses(
    live_report: ContractReviewReport,
) -> None:
    """Thai headings must survive the real parse -> segment path.

    Segmentation doesn't call the model, so this is deterministic - it is here
    because the document is Thai and the heading rules are the reason it works
    at all.
    """
    assert len(live_report.reviews) == 3


def test_risk_levels_are_answers_rather_than_defaults(
    live_report: ContractReviewReport,
) -> None:
    """At least one clause must be scored.

    The NDA holds unlimited, uncapped liability and a perpetual confidentiality
    obligation, so a run where every clause came back ``unknown`` is a broken
    pipeline rather than a lenient contract.
    """
    scored = [
        review for review in live_report.reviews if review.risk_level is not RiskLevel.UNKNOWN
    ]
    assert scored, "every clause came back unknown; the pipeline scored nothing"


def test_citations_point_at_real_playbook_positions(
    live_report: ContractReviewReport,
    known_positions: dict[str, PlaybookPosition],
) -> None:
    """A citation to a position that doesn't exist is an invented source."""
    known_ids = set(known_positions)
    for review in live_report.reviews:
        unknown = invalid_citations(review, known_ids)
        assert not unknown, f"clause {review.clause.id} cites unknown position(s): {unknown}"


def test_citation_excerpts_are_verbatim_quotes(
    live_report: ContractReviewReport,
    known_positions: dict[str, PlaybookPosition],
) -> None:
    """Excerpts must be quoted from the cited position, not paraphrased.

    The judge enforces this at review time, so a violation here means the
    guardrail and the pipeline disagree - the report reached the reviewer
    carrying a quote the judge would have rejected.
    """
    for review in live_report.reviews:
        for citation in review.citations:
            position = known_positions[citation.playbook_position_id]
            source = f"{position.preferred_language} {position.fallback_language}"
            assert is_grounded(citation.excerpt, source, min_words=MIN_CITATION_EXCERPT_WORDS), (
                f"clause {review.clause.id} citation {citation.citation_id} is not a "
                f"verbatim quote of >= {MIN_CITATION_EXCERPT_WORDS} words from "
                f"{position.id}: {citation.excerpt!r}"
            )


def test_suggested_fallbacks_come_from_the_playbook(
    live_report: ContractReviewReport,
    known_positions: dict[str, PlaybookPosition],
) -> None:
    """Suggested wording must be the playbook's, not the model's own drafting."""
    positions = list(known_positions.values())
    for review in live_report.reviews:
        assert is_allowed_fallback(review.suggested_fallback, positions), (
            f"clause {review.clause.id} suggests wording that is in no playbook "
            f"position: {review.suggested_fallback!r}"
        )


def test_verified_clauses_carry_the_judges_approval(
    live_report: ContractReviewReport,
) -> None:
    """``verified`` must mean a judge said so, and a judged clause must be sound.

    The badge the UI shows as "ตรวจสอบแล้ว". A clause the judge passed cannot
    also be one the pipeline gave up on, and a clause marked verified with no
    rationale is a badge with nothing behind it.
    """
    for review in live_report.reviews:
        if review.verified:
            assert review.rationale.strip(), (
                f"clause {review.clause.id} is marked verified but has no rationale"
            )
            assert _FAILURE_RATIONALE not in review.rationale


def test_contract_metadata_is_quoted_from_the_document(
    live_report: ContractReviewReport,
    sample_document: ParsedDocument,
) -> None:
    """Header facts must be findable in the file, word for word.

    Empty is allowed and is a real answer - the rule is that whatever *is*
    reported was read out of the document rather than inferred. The NDA names
    both companies in its opening line, so a run that reports no parties at
    all is worth failing on.
    """
    metadata = live_report.metadata
    values = [
        *metadata.parties,
        metadata.agreement_date,
        metadata.effective_date,
        metadata.expiration_date,
        metadata.contract_value,
        metadata.governing_law,
    ]
    for value in values:
        if value:
            assert is_grounded(value, sample_document.text), (
                f"metadata value is not verbatim in the document: {value!r}"
            )

    assert metadata.parties, "the NDA names both parties in its first paragraph"


def test_the_report_carries_its_disclaimer(live_report: ContractReviewReport) -> None:
    """Machine-generated risk advice never ships without it."""
    assert live_report.disclaimer.strip()
