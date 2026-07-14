"""Session-scoped storage for generated review reports."""

from __future__ import annotations

from app.schemas.report import ContractReviewReport


class ReportRepository:
    """Stores review reports for the lifetime of a session."""

    def __init__(self) -> None:
        self._store: dict[str, ContractReviewReport] = {}

    def save(self, report: ContractReviewReport) -> None:
        """Persist ``report`` keyed by its ``report_id``."""
        self._store[report.report_id] = report

    def get(self, report_id: str) -> ContractReviewReport | None:
        """Return the report, or ``None`` if absent/expired."""
        return self._store.get(report_id)
