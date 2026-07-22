"""Contract review + override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import get_current_user, get_override_service, get_review_service
from app.models import User
from app.schemas.report import ContractReviewReport
from app.schemas.taxonomy import RiskLevel
from app.services.override_service import OverrideService
from app.services.review_service import ReviewService

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("/review", response_model=ContractReviewReport)
async def review_contract(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> ContractReviewReport:
    """Upload a contract and run the review pipeline."""
    data = await file.read()
    return service.review_upload(
        filename=file.filename or "upload",
        data=data,
        session_id=current_user.id,
    )


@router.post("/{report_id}/override", response_model=ContractReviewReport)
async def override_clause(
    report_id: str,
    clause_id: str,
    new_risk: RiskLevel,
    reason: str,
    current_user: User = Depends(get_current_user),
    service: OverrideService = Depends(get_override_service),
) -> ContractReviewReport:
    """Apply a human override to a clause's risk assessment."""
    return service.override_risk(
        report_id=report_id,
        clause_id=clause_id,
        new_risk=new_risk,
        reason=reason,
        actor=current_user.email,
    )
