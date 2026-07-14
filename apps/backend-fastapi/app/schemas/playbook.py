"""Playbook position and retrieval models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.taxonomy import ClauseType, RiskLevel


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
