"""Session-scoped storage for generated review reports."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.report import ContractReviewReport


class ReportRepository:
    """Stores review reports for the lifetime of a session."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[ContractReviewReport, datetime]] = {}

    def save(self, report: ContractReviewReport) -> None:
        """Persist ``report`` keyed by its ``report_id``."""
        self._store[report.report_id] = (report, datetime.utcnow())

    def get(self, report_id: str) -> ContractReviewReport | None:
        """Return the report, or ``None`` if absent/expired."""
        entry = self._store.get(report_id)
        return entry[0] if entry else None

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        """Remove ``session_id``'s reports older than ``ttl_seconds``; return their ids."""
        cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)
        expired = [
            report_id
            for report_id, (report, saved_at) in self._store.items()
            if report.session_id == session_id and saved_at < cutoff
        ]
        for report_id in expired:
            del self._store[report_id]
        return expired
