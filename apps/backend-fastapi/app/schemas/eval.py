"""Evaluation request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
