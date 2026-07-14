"""Evaluation endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.eval import EvalMetrics, EvalRequest

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=EvalMetrics)
async def evaluate(request: EvalRequest) -> EvalMetrics:
    """Run the evaluation harness against a gold set.

    TODO: delegate to ``EvalService.run`` (via DI).
    """
    raise NotImplementedError
