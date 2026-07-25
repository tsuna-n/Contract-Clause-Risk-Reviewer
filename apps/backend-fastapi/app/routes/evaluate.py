"""Evaluation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_eval_service
from app.schemas import EvalMetrics, EvalRequest
from app.services.evaluation import EvalService

router = APIRouter(tags=["evaluate"])


@router.post("/evaluate", response_model=EvalMetrics)
async def evaluate(
    request: EvalRequest,
    service: EvalService = Depends(get_eval_service),
) -> EvalMetrics:
    """Run the evaluation harness against a gold set."""
    return service.run(request)
