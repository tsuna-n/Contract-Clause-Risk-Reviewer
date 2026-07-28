"""Contract review, history + override endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies import (
    get_current_user,
    get_override_service,
    get_report_service,
    get_review_service,
)
from app.models import User
from app.schemas import ContractReviewReport, OverrideRequest, ReportSummary
from app.services.override import OverrideService
from app.services.report import ReportService
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


@router.get("", response_model=list[ReportSummary])
async def list_reports(
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> list[ReportSummary]:
    """List this session's reviews, newest first.

    Summaries, not whole reports: this is what draws the history sidebar, and
    a list of full reports would be megabytes of clause text nothing renders.
    """
    return service.list_history(current_user.id)


@router.get(
    "/{report_id}",
    response_model=ContractReviewReport,
    response_model_exclude=_INTERNAL_REPORT_FIELDS,
)
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> ContractReviewReport:
    """Return one stored report in full."""
    return service.get_report(report_id, session_id=current_user.id)


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
        session_id=current_user.id,
    )


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> None:
    """Delete one stored review report."""
    service.delete_report(report_id, session_id=current_user.id)

