"""Override service: apply a human override and write the audit log."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.pipeline import aggregate
from app.errors import NotFoundError
from app.repositories.audit import AuditRepository, OverrideRecord
from app.repositories.report import ReportRepository
from app.schemas import ContractReviewReport, RiskLevel


class OverrideService:
    """Applies human overrides to a report and records them for audit."""

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
        """Override a clause's risk level and append an audit record.

        ``session_id`` scopes the write to the caller's own reports. Report ids
        are unguessable, but "unguessable" is not an access control: without
        this check any signed-in user who came by an id could rewrite someone
        else's risk assessment and sign the audit trail with their own name.
        A report owned by another session reads as missing, for the same reason
        it does in :class:`~app.services.report.ReportService`.
        """
        report = self.reports.get(report_id)
        if report is None or report.session_id != session_id:
            raise NotFoundError(f"report {report_id} not found")

        match = next((r for r in report.reviews if r.clause.id == clause_id), None)
        if match is None:
            raise NotFoundError(f"clause {clause_id} not found in report {report_id}")

        old_risk = match.risk_level
        match.risk_level = new_risk
        match.verified = True

        report.summary, report.overall_risk = aggregate(report.reviews)
        self.reports.save(report)

        self.audit.append(
            OverrideRecord(
                report_id=report_id,
                clause_id=clause_id,
                old_risk=old_risk,
                new_risk=new_risk,
                reason=reason,
                actor=actor,
                created_at=datetime.now(UTC),
            )
        )
        return report
