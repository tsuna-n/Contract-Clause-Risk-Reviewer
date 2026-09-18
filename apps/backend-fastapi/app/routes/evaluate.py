"""Evaluation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_eval_service, get_redis_client
from app.models import User
from app.schemas import EvalJob, EvalMetrics, EvalRequest
from app.services.eval_jobs import EvalJobs
from app.services.evaluation import EvalService

# Public until 2026-07-30, which meant anyone could spend the project's LLM
# quota a full gold set at a time.
router = APIRouter(tags=["evaluate"], dependencies=[Depends(get_current_user)])


def get_eval_jobs() -> EvalJobs:
    return EvalJobs(get_redis_client())


@router.post("/evaluate/jobs", response_model=EvalJob, status_code=202)
def start_evaluation(
    request: EvalRequest,
    user: User = Depends(get_current_user),
    service: EvalService = Depends(get_eval_service),
    jobs: EvalJobs = Depends(get_eval_jobs),
) -> EvalJob:
    return jobs.start(request, user.id, service)


@router.get("/evaluate/jobs/{job_id}", response_model=EvalJob)
def evaluation_progress(
    job_id: str,
    user: User = Depends(get_current_user),
    jobs: EvalJobs = Depends(get_eval_jobs),
) -> EvalJob:
    return jobs.get(job_id, user.id)


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
