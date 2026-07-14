"""Override service: apply a human override and write the audit log."""

from __future__ import annotations

from app.repositories.audit_repo import AuditRepository
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
        """Override a clause's risk level and append an audit record.

        TODO: load the report, update the matching ClauseReview, append an
        OverrideRecord to the audit log, re-aggregate the summary, and persist.
        """
        raise NotImplementedError
