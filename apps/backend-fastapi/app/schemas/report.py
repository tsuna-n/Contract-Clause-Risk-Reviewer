"""Contract-level review report models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.clause import ClauseReview
from app.schemas.taxonomy import RiskLevel


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    overall_risk: RiskLevel = RiskLevel.UNKNOWN
    summary: RiskSummary = Field(default_factory=RiskSummary)
    reviews: list[ClauseReview] = Field(default_factory=list)
    disclaimer: str = ""
