"""Session-scoped storage for generated review reports (in-memory / redis)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from app.schemas.report import ContractReviewReport


class ReportRepository(Protocol):
    """Storage interface for review reports, scoped to a single session.

    :class:`InMemoryReportRepository` and :class:`RedisReportRepository`
    both satisfy this interface.
    """

    def save(self, report: ContractReviewReport) -> None:
        """Persist ``report`` keyed by its ``report_id``."""
        ...

    def get(self, report_id: str) -> ContractReviewReport | None:
        """Return the report, or ``None`` if absent/expired."""
        ...

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        """Remove ``session_id``'s reports older than ``ttl_seconds``; return their ids."""
        ...


class InMemoryReportRepository:
    """Process-local dict-backed store.

    Fine for a single worker process; does not share state across
    processes/replicas — see :class:`RedisReportRepository` for that. Unlike
    Redis, this store has no expiry of its own, so ``purge_expired`` has to
    be called (see ``core.retention.enforce_retention``) to actually drop
    old entries.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[ContractReviewReport, datetime]] = {}

    def save(self, report: ContractReviewReport) -> None:
        self._store[report.report_id] = (report, datetime.utcnow())

    def get(self, report_id: str) -> ContractReviewReport | None:
        entry = self._store.get(report_id)
        return entry[0] if entry else None

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)
        expired = [
            report_id
            for report_id, (report, saved_at) in self._store.items()
            if report.session_id == session_id and saved_at < cutoff
        ]
        for report_id in expired:
            del self._store[report_id]
        return expired


class RedisReportRepository:
    """Redis-backed :class:`ReportRepository`.

    Reports are stored with a native Redis TTL (``ex=ttl_seconds`` at save
    time), so — unlike the in-memory store — expiry doesn't depend on a
    sweep ever running again for that session: Redis drops the key on its
    own even if the session is never touched again. ``purge_expired`` is
    kept as a no-op purely to satisfy the shared interface, since
    ``core.retention.enforce_retention`` calls it unconditionally on every
    upload regardless of which backend is wired in.
    """

    def __init__(self, client: Any, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(report_id: str) -> str:
        return f"report:{report_id}"

    def save(self, report: ContractReviewReport) -> None:
        self._client.set(
            self._key(report.report_id), report.model_dump_json(), ex=self._ttl_seconds
        )

    def get(self, report_id: str) -> ContractReviewReport | None:
        data = self._client.get(self._key(report_id))
        return ContractReviewReport.model_validate_json(data) if data is not None else None

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        return []
