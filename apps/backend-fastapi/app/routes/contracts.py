"""Contract review + override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies import get_current_user, get_override_service, get_review_service
from app.models import User
from app.schemas import ContractReviewReport, OverrideRequest
from app.services.override import OverrideService
from app.services.review import ReviewService

router = APIRouter(prefix="/contracts", tags=["contracts"])

# ``session_id`` is the owner's Google ``sub``. The report model carries it for
# session-scoped purging, but the browser already knows who it is signed in as
# and never reads the field - so it stays server-side rather than being echoed
# into every response.
_INTERNAL_REPORT_FIELDS = {"session_id"}


@router.post(
    "/review",
    response_model=ContractReviewReport,
    response_model_exclude=_INTERNAL_REPORT_FIELDS,
)
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


@router.post(
    "/{report_id}/override",
    response_model=ContractReviewReport,
    response_model_exclude=_INTERNAL_REPORT_FIELDS,
)
async def override_clause(
    report_id: str,
    payload: OverrideRequest,
    current_user: User = Depends(get_current_user),
    service: OverrideService = Depends(get_override_service),
) -> ContractReviewReport:
    """Apply a human override to a clause's risk assessment."""
    return service.override_risk(
        report_id=report_id,
        clause_id=payload.clause_id,
        new_risk=payload.new_risk,
        reason=payload.reason,
        actor=current_user.email,
    )
