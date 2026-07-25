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


class RetrievalHit(BaseModel):
    """A single scored retrieval result."""

    position: PlaybookPosition
    score: float
    source: str = "hybrid"  # bm25 | dense | hybrid


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
    verified: bool = False


# --- reports -----------------------------------------------------------------


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
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_risk: RiskLevel = RiskLevel.UNKNOWN
    summary: RiskSummary = Field(default_factory=RiskSummary)
    reviews: list[ClauseReview] = Field(default_factory=list)
    disclaimer: str = ""


# --- evaluation --------------------------------------------------------------


class EvalRequest(BaseModel):
    """Request to run the evaluation harness against a gold set."""

    gold_set_path: str = "data/gold/annotations.jsonl"
    limit: int | None = None


class PerTypeMetrics(BaseModel):
    """Per-clause-type breakdown of accuracy."""

    clause_type: str
    support: int
    accuracy: float


class EvalMetrics(BaseModel):
    """Aggregate evaluation metrics."""

    segmentation_f1: float = 0.0
    classification_accuracy: float = 0.0
    risk_accuracy: float = 0.0
    citation_validity: float = 0.0
    per_type: list[PerTypeMetrics] = Field(default_factory=list)


# --- users -------------------------------------------------------------------


class UserOut(BaseModel):
    """The signed-in user as returned by ``GET /auth/me``."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    picture: str | None = None
