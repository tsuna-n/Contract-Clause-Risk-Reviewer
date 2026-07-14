"""Contract review + override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from app.schemas.report import ContractReviewReport
from app.schemas.taxonomy import RiskLevel

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("/review", response_model=ContractReviewReport)
async def review_contract(file: UploadFile) -> ContractReviewReport:
    """Upload a contract and run the review pipeline.

    TODO: read the upload, resolve the session id, and delegate to
    ``ReviewService.review_upload`` (via a DI dependency).
    """
    raise NotImplementedError


@router.post("/{report_id}/override", response_model=ContractReviewReport)
async def override_clause(
    report_id: str,
    clause_id: str,
    new_risk: RiskLevel,
    reason: str,
) -> ContractReviewReport:
    """Apply a human override to a clause's risk assessment.

    TODO: delegate to ``OverrideService.override_risk`` (via DI).
    """
    raise NotImplementedError
