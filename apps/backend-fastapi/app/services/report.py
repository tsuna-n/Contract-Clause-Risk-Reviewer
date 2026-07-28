"""Report service: read back the reviews a session has already produced.

The review pipeline stores every report it generates, but until now nothing
could fetch one again — a reviewer who reloaded the page lost the review and
had to pay for the whole pipeline a second time. This is the read side.

Ownership lives here rather than in the repository: storage answers "does this
report exist", and only the service layer knows who is asking.
"""

from __future__ import annotations

from app.errors import NotFoundError
from app.repositories.report import ReportRepository
from app.schemas import ContractReviewReport, ReportSummary


class ReportService:
    """Lists and fetches a session's stored review reports."""

    def __init__(self, reports: ReportRepository) -> None:
        self.reports = reports

    def list_history(self, session_id: str) -> list[ReportSummary]:
        """Return this session's reviews, newest first."""
        return [ReportSummary.of(report) for report in self.reports.list_for_session(session_id)]

    def get_report(self, report_id: str, session_id: str) -> ContractReviewReport:
        """Return one of this session's reports.

        Someone else's report is reported as missing, not as forbidden: a 403
        would confirm that ``report_id`` exists, which is exactly the fact a
        caller guessing ids is trying to learn.
        """
        report = self.reports.get(report_id)
        if report is None or report.session_id != session_id:
            raise NotFoundError(f"report {report_id} not found")
        return report

    def delete_report(self, report_id: str, session_id: str) -> None:
        """Delete one of this session's reports or raise NotFoundError."""
        success = self.reports.delete(report_id, session_id)
        if not success:
            raise NotFoundError(f"report {report_id} not found")
