"""Session-scoped storage for generated review reports (in-memory / redis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.schemas import ContractReviewReport


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

    def list_for_session(self, session_id: str) -> list[ContractReviewReport]:
        """Return ``session_id``'s live reports, newest first."""
        ...

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        """Remove ``session_id``'s reports older than ``ttl_seconds``; return their ids."""
        ...

    def delete(self, report_id: str, session_id: str) -> bool:
        """Delete ``report_id`` if owned by ``session_id``; return True if deleted."""
        ...


class InMemoryReportRepository:
    """Process-local dict-backed store.

    Fine for a single worker process; does not share state across
    processes/replicas — see :class:`RedisReportRepository` for that. Unlike
    Redis, this store has no expiry of its own, so ``purge_expired`` has to
    be called (``ReviewService`` does, on every upload) to actually drop old
    entries.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[ContractReviewReport, datetime]] = {}

    def save(self, report: ContractReviewReport) -> None:
        self._store[report.report_id] = (report, datetime.now(UTC))

    def get(self, report_id: str) -> ContractReviewReport | None:
        entry = self._store.get(report_id)
        return entry[0] if entry else None

    def list_for_session(self, session_id: str) -> list[ContractReviewReport]:
        reports = [report for report, _ in self._store.values() if report.session_id == session_id]
        return sorted(reports, key=lambda report: report.created_at, reverse=True)

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        cutoff = datetime.now(UTC) - timedelta(seconds=ttl_seconds)
        expired = [
            report_id
            for report_id, (report, saved_at) in self._store.items()
            if report.session_id == session_id and saved_at < cutoff
        ]
        for report_id in expired:
            del self._store[report_id]
        return expired

    def delete(self, report_id: str, session_id: str) -> bool:
        entry = self._store.get(report_id)
        if entry is not None and entry[0].session_id == session_id:
            del self._store[report_id]
            return True
        return False


class RedisReportRepository:
    """Redis-backed :class:`ReportRepository`.

    Reports are stored with a native Redis TTL (``ex=ttl_seconds`` at save
    time), so — unlike the in-memory store — expiry doesn't depend on a
    sweep ever running again for that session: Redis drops the key on its
    own even if the session is never touched again. ``purge_expired`` is
    kept as a no-op purely to satisfy the shared interface, since
    ``ReviewService`` calls it unconditionally on every upload regardless of
    which backend is wired in.

    A per-session sorted set indexes the reports so history can be listed
    without scanning the keyspace: ``KEYS report:*`` is O(all reports) and
    blocks the server, and it still couldn't tell whose reports they were
    without fetching every one of them.
    """

    def __init__(self, client: Any, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(report_id: str) -> str:
        return f"report:{report_id}"

    @staticmethod
    def _index_key(session_id: str) -> str:
        return f"session:{session_id}:reports"

    def save(self, report: ContractReviewReport) -> None:
        self._client.set(
            self._key(report.report_id), report.model_dump_json(), ex=self._ttl_seconds
        )
        index_key = self._index_key(report.session_id)
        # Scored by creation time, so the index reads back newest-first without
        # deserializing a single report.
        self._client.zadd(index_key, {report.report_id: report.created_at.timestamp()})
        # The index has to outlive its newest member or a live report would
        # vanish from history early. Re-setting the TTL on every save keeps it
        # a full retention window ahead of the last write.
        self._client.expire(index_key, self._ttl_seconds)

    def get(self, report_id: str) -> ContractReviewReport | None:
        data = self._client.get(self._key(report_id))
        return ContractReviewReport.model_validate_json(data) if data is not None else None

    def list_for_session(self, session_id: str) -> list[ContractReviewReport]:
        index_key = self._index_key(session_id)
        reports: list[ContractReviewReport] = []
        dangling: list[str] = []

        for report_id in self._client.zrevrange(index_key, 0, -1):
            report = self.get(report_id)
            if report is None:
                # The report's own TTL fired first. Drop the index entry rather
                # than listing a review that can no longer be opened.
                dangling.append(report_id)
            else:
                reports.append(report)

        if dangling:
            self._client.zrem(index_key, *dangling)
        return reports

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        return []

    def delete(self, report_id: str, session_id: str) -> bool:
        report = self.get(report_id)
        if report is None or report.session_id != session_id:
            return False
        self._client.delete(self._key(report_id))
        self._client.zrem(self._index_key(session_id), report_id)
        return True
