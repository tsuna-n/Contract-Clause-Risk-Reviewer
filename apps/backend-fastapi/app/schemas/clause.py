"""Clause and per-clause review models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.taxonomy import ClauseType, RiskLevel


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
