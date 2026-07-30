"""Evaluation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_eval_service
from app.schemas import EvalMetrics, EvalRequest
from app.services.evaluation import EvalService

# Public until 2026-07-30, which meant anyone could spend the project's LLM
# quota a full gold set at a time.
router = APIRouter(tags=["evaluate"], dependencies=[Depends(get_current_user)])


@router.post("/evaluate", response_model=EvalMetrics)
def evaluate(
    request: EvalRequest,
    service: EvalService = Depends(get_eval_service),
) -> EvalMetrics:
    """Run the evaluation harness against a gold set.

    Deliberately not ``async``: this runs the whole pipeline over every
    contract in the gold set, which is minutes of blocking work per contract.
    A sync endpoint gets its own worker thread instead of holding the event
    loop for the entire run.
    """
    return service.run(request)
