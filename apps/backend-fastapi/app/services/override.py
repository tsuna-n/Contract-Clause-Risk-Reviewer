"""Reviewer decisions on a stored report: overrides and sign-offs.

Both live here because both are the same operation with a different verdict —
find the caller's report, find the clause, change it, save, and leave a record
in the audit log. Splitting them would duplicate the ownership check, which is
the part that must never diverge.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.pipeline import aggregate
from app.errors import NotFoundError
from app.repositories.audit import AuditAction, AuditRepository, OverrideRecord
from app.repositories.report import ReportRepository
from app.schemas import ClauseReview, ContractReviewReport, RiskLevel


class OverrideService:
    """Applies human overrides and acceptances to a report, and audits them."""

    def __init__(self, reports: ReportRepository, audit: AuditRepository) -> None:
        self.reports = reports
        self.audit = audit

    def override_risk(
        self,
        *,
        report_id: str,
        clause_id: str,
        new_risk: RiskLevel,
        reason: str,
        actor: str,
        session_id: str,
    ) -> ContractReviewReport:
        """Override a clause's risk level and append an audit record."""
        report, match = self._locate(report_id, clause_id, session_id)

        old_risk = match.risk_level
        match.risk_level = new_risk
        match.verified = True
        # The reviewer just disagreed with this assessment, so any earlier
        # sign-off was for a different verdict and no longer stands.
        match.accepted = False
        match.accepted_by = None
        match.accepted_at = None

        report.summary, report.overall_risk = aggregate(report.reviews)
        self.reports.save(report)

        self.audit.append(
            OverrideRecord(
                report_id=report_id,
                clause_id=clause_id,
                action=AuditAction.OVERRIDE,
                old_risk=old_risk,
                new_risk=new_risk,
                reason=reason,
                actor=actor,
                created_at=datetime.now(UTC),
            )
        )
        return report

    def accept_clause(
        self,
        *,
        report_id: str,
        clause_id: str,
        accepted: bool,
        note: str | None,
        actor: str,
        session_id: str,
    ) -> ContractReviewReport:
        """Record (or withdraw) a reviewer's sign-off on one clause.

        Risk levels and the report summary are untouched: accepting means "I
        agree with what it says", so changing the numbers would misreport what
        the reviewer actually did. What changes is who is on the hook for it.
        """
        report, match = self._locate(report_id, clause_id, session_id)

        now = datetime.now(UTC)
        match.accepted = accepted
        match.accepted_by = actor if accepted else None
        match.accepted_at = now if accepted else None
        self.reports.save(report)

        self.audit.append(
            OverrideRecord(
                report_id=report_id,
                clause_id=clause_id,
                action=AuditAction.ACCEPT if accepted else AuditAction.UNACCEPT,
                # Unchanged on both sides - an acceptance names the assessment
                # it vouches for rather than replacing it.
                old_risk=match.risk_level,
                new_risk=match.risk_level,
                reason=note or ("accepted as assessed" if accepted else "acceptance withdrawn"),
                actor=actor,
                created_at=now,
            )
        )
        return report

    def _locate(
        self, report_id: str, clause_id: str, session_id: str
    ) -> tuple[ContractReviewReport, ClauseReview]:
        """Return the caller's report and the clause review inside it.

        ``session_id`` scopes every write to the caller's own reports. Report
        ids are unguessable, but "unguessable" is not an access control:
        without this check any signed-in user who came by an id could rewrite
        someone else's risk assessment and sign the audit trail with their own
        name. A report owned by another session reads as missing, for the same
        reason it does in :class:`~app.services.report.ReportService`.
        """
        report = self.reports.get(report_id)
        if report is None or report.session_id != session_id:
            raise NotFoundError(f"report {report_id} not found")

        match = next((r for r in report.reviews if r.clause.id == clause_id), None)
        if match is None:
            raise NotFoundError(f"clause {clause_id} not found in report {report_id}")
        return report, match
