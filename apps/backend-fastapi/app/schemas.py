"""Pydantic schemas — the shapes that travel over HTTP and between layers.

Grouped in one module because they are read together: a report contains clause
reviews, a clause review cites playbook positions, and everything is labelled
with the shared taxonomy enums below.

ORM tables live in ``app/models.py``; these are the API/DTO counterparts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# --- taxonomy ----------------------------------------------------------------


class ClauseType(StrEnum):
    """Supported clause categories.

    This enum is the single source of truth for the taxonomy: the classifier
    prompt is built from ``[t.value for t in ClauseType]``, so adding a member
    here is all it takes to teach the pipeline a new category.
    """

    CONFIDENTIALITY = "confidentiality"  # Obligations to keep shared information secret.
    INDEMNIFICATION = "indemnification"  # One party covers losses/claims incurred by the other.
    LIMITATION_OF_LIABILITY = "limitation_of_liability"  # Caps or excludes a party's liability.
    TERMINATION = "termination"  # How and when the agreement can be ended.
    GOVERNING_LAW = "governing_law"  # Which jurisdiction's law governs the contract.
    INTELLECTUAL_PROPERTY = "intellectual_property"  # Ownership and licensing of IP.
    PAYMENT_TERMS = "payment_terms"  # Amounts, schedule, and conditions of payment.
    WARRANTY = "warranty"  # Assurances about goods/services provided.
    NON_COMPETE = "non_compete"  # Restrictions on competing activities.
    DATA_PROTECTION = "data_protection"  # Handling of personal/sensitive data.
    FORCE_MAJEURE = "force_majeure"  # Excused performance due to extraordinary events.
    OTHER = "other"  # Anything not covered by the categories above.


class RiskLevel(StrEnum):
    """Risk rating assigned to a clause."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RetrievalSource(StrEnum):
    """How a retrieval hit was scored.

    Only the two strategies :class:`~app.ai.retrieval.Retriever` actually
    emits. BM25 is deliberately absent: it never stands alone, it reranks the
    dense candidate pool, and that blend is what ``HYBRID`` means.
    """

    DENSE = "dense"  # Vector similarity alone (hybrid retrieval disabled).
    HYBRID = "hybrid"  # Dense candidates reranked by a BM25 lexical score.


# --- playbook ----------------------------------------------------------------


class PlaybookPosition(BaseModel):
    """A company position on how a clause type should be handled."""

    id: str
    clause_type: ClauseType
    title: str
    preferred_language: str
    fallback_language: str
    risk_if_absent: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = Field(default_factory=list)


class PlaybookPositionCreate(BaseModel):
    """Payload for creating a playbook position.

    ``id`` is optional: the repository generates one (``pb_<short>``) when the
    caller leaves it blank, so the API accepts a position without forcing the
    client to invent a stable identifier first.
    """

    id: str | None = None
    clause_type: ClauseType
    title: str
    preferred_language: str
    fallback_language: str
    risk_if_absent: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = Field(default_factory=list)


class PlaybookPositionUpdate(BaseModel):
    """Partial update for a playbook position.

    Every field is optional — a ``None`` means "leave unchanged", which the
    repository turns into a skipped assignment. This is why the update route
    can accept a body with only the fields a reviewer actually edited.
    """

    clause_type: ClauseType | None = None
    title: str | None = None
    preferred_language: str | None = None
    fallback_language: str | None = None
    risk_if_absent: RiskLevel | None = None
    tags: list[str] | None = None


class RetrievalHit(BaseModel):
    """A single scored retrieval result."""

    position: PlaybookPosition
    score: float
    source: RetrievalSource = RetrievalSource.HYBRID


# --- clauses -----------------------------------------------------------------


class Span(BaseModel):
    """Character offset range into the normalized document text."""

    start: int
    end: int
    page: int | None = None


class Clause(BaseModel):
    """A segmented clause extracted from a contract."""

    id: str
    text: str
    span: Span
    clause_type: ClauseType = ClauseType.OTHER
    heading: str | None = None


class Citation(BaseModel):
    """A reference to a playbook position backing a risk assessment."""

    citation_id: str
    playbook_position_id: str
    excerpt: str


class ClauseReview(BaseModel):
    """The reviewer's assessment of a single clause."""

    clause: Clause
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    rationale: str = ""
    citations: list[Citation] = Field(default_factory=list)
    suggested_fallback: str | None = None
    # The judge's grounding verdict on the machine's own rationale.
    verified: bool = False
    # A person read this clause and signed off on the assessment as it stands.
    # Distinct from ``verified``: that is the pipeline checking itself, this is
    # a human taking responsibility, and it is what turns a report into a piece
    # of work someone can resume. Reversible - see ``AcceptRequest``.
    accepted: bool = False
    # Who accepted, and when. Absent while ``accepted`` is False.
    accepted_by: str | None = None
    accepted_at: datetime | None = None


# --- reports -----------------------------------------------------------------


class ContractMetadata(BaseModel):
    """Facts about the contract as a whole, quoted from the document.

    Every value is text copied verbatim out of the uploaded file, and anything
    the extractor returns that isn't found in the document is dropped before
    it reaches here — the same no-invention rule the clause reviews live under,
    applied to the header panel. Empty is a correct answer: a blank "Parties"
    row is a document that doesn't name them, and that beats a plausible guess
    a reviewer would have no reason to doubt.

    Dates are strings, not ``date`` objects, on purpose. Contracts write dates
    as "the 3rd day of March, 2019" or "3/4/19", and parsing either one means
    choosing an interpretation (which day? which convention?) that the reviewer
    can no longer see or check. The document's own wording is the fact.
    """

    parties: list[str] = Field(default_factory=list)
    agreement_date: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    contract_value: str | None = None
    governing_law: str | None = None

    def is_empty(self) -> bool:
        """True when the extractor found nothing to report."""
        return not any(
            [
                self.parties,
                self.agreement_date,
                self.effective_date,
                self.expiration_date,
                self.contract_value,
                self.governing_law,
            ]
        )


class RiskSummary(BaseModel):
    """Aggregate risk counts for a report."""

    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0


class ContractReviewReport(BaseModel):
    """The full result of reviewing a contract."""

    report_id: str
    contract_id: str
    # Whose report this is - the signed-in user's Google ``sub``. Internal:
    # ``ReportRepository.purge_expired`` needs it to scope a session's reports,
    # but it is an account identifier with no use in the browser, so the routes
    # strip it from the HTTP response (``response_model_exclude``). It still
    # round-trips through Redis, which is what purging relies on.
    session_id: str
    # The uploaded file's name. The only piece of contract metadata the
    # pipeline knows for certain (it came with the request rather than being
    # read out of the document), and what the history list is labelled with -
    # "a report" with no name is not something a reviewer can pick from a list.
    filename: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_risk: RiskLevel = RiskLevel.UNKNOWN
    summary: RiskSummary = Field(default_factory=RiskSummary)
    reviews: list[ClauseReview] = Field(default_factory=list)
    # Who signed what, when, for how much - read out of the document itself.
    # Defaults to empty, which is what a report saved before extraction
    # existed (or one where the pipeline found nothing) reads back as.
    metadata: ContractMetadata = Field(default_factory=ContractMetadata)
    disclaimer: str = ""


class ReportSummary(BaseModel):
    """One row of review history - a report without its clause reviews.

    The history list renders dozens of these at once and shows none of the
    clause detail, so sending whole reports would move megabytes to draw a
    sidebar. ``GET /contracts/{report_id}`` returns the full thing.
    """

    report_id: str
    contract_id: str
    filename: str = ""
    created_at: datetime
    overall_risk: RiskLevel = RiskLevel.UNKNOWN
    summary: RiskSummary = Field(default_factory=RiskSummary)
    clause_count: int = 0

    @classmethod
    def of(cls, report: ContractReviewReport) -> ReportSummary:
        """Summarize a full report for the history list."""
        return cls(
            report_id=report.report_id,
            contract_id=report.contract_id,
            filename=report.filename,
            created_at=report.created_at,
            overall_risk=report.overall_risk,
            summary=report.summary,
            clause_count=len(report.reviews),
        )


class OverrideRequest(BaseModel):
    """A reviewer's correction to one clause's risk level.

    A body rather than query params: ``reason`` is free-form text a person
    types, and a URL is the wrong place for it - it lands in access logs,
    browser history, and ``Referer`` headers, and the audit trail is exactly
    the data that shouldn't leak into those. The bounds keep an unbounded
    string out of the audit table.
    """

    clause_id: str = Field(min_length=1)
    new_risk: RiskLevel
    reason: str = Field(min_length=1, max_length=1000)


class AcceptRequest(BaseModel):
    """A reviewer signing off on one clause's assessment - or taking it back.

    ``accepted=False`` un-accepts, because sign-off is a claim a person made
    and misclicking it must be undoable. Both directions are audited, so the
    log shows the retraction rather than quietly losing the first record.

    ``note`` is optional here, unlike ``OverrideRequest.reason``: disagreeing
    with the model is a judgement that needs explaining, agreeing with it is
    not.
    """

    clause_id: str = Field(min_length=1)
    accepted: bool = True
    note: str | None = Field(default=None, max_length=1000)


# --- evaluation --------------------------------------------------------------


class EvalRequest(BaseModel):
    """Request to run the evaluation harness against a gold set."""

    gold_set_path: str = "data/gold/annotations.jsonl"
    limit: int | None = None


class PerTypeMetrics(BaseModel):
    """Per-clause-type breakdown of accuracy."""

    # The taxonomy enum, not a bare string: these rows are keyed by labels read
    # out of the gold-set file, so validating here turns a typo'd annotation
    # into an error instead of a silent extra category with its own metrics.
    clause_type: ClauseType
    support: int
    accuracy: float


class EvalMetrics(BaseModel):
    """Aggregate evaluation metrics."""

    segmentation_f1: float = 0.0
    classification_accuracy: float = 0.0
    risk_accuracy: float = 0.0
    citation_validity: float = 0.0
    per_type: list[PerTypeMetrics] = Field(default_factory=list)
    #: ``gold clause type -> predicted clause type -> count``. Reported because
    #: the accuracy figure alone cannot distinguish "the classifier is wrong"
    #: from "the gold label is" — and with CUAD-derived labels, both happen.
    classification_confusion: dict[str, dict[str, int]] = Field(default_factory=dict)


# --- users -------------------------------------------------------------------


class UserOut(BaseModel):
    """The signed-in user as returned by ``GET /auth/me``."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    picture: str | None = None
