"""Override service: apply a human override and write the audit log."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.orchestrator import aggregate
from app.core.exceptions import NotFoundError
from app.repositories.audit_repo import AuditRepository, OverrideRecord
from app.repositories.report_repo import ReportRepository
from app.schemas.report import ContractReviewReport
from app.schemas.taxonomy import RiskLevel


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
    ) -> ContractReviewReport:
        """Override a clause's risk level and append an audit record."""
        report = self.reports.get(report_id)
        if report is None:
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
