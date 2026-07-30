"""Storage for generated review reports (in-memory / redis / postgres)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models import ContractReport
from app.schemas import ContractReviewReport, ReportSummary


class ReportRepository(Protocol):
    """Storage interface for review reports, scoped to a single session.

    :class:`InMemoryReportRepository`, :class:`RedisReportRepository` and
    :class:`PostgresReportRepository` all satisfy this interface. The first
    two are ephemeral (a process, or a retention window); the third is the
    durable one and what ``REPORT_STORAGE`` selects by default.
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

    def list_summaries(self, session_id: str) -> list[ReportSummary]:
        """Return ``session_id``'s reports as history rows, newest first.

        Separate from :meth:`list_for_session` because the history sidebar
        needs six fields per report and none of the clause text. A durable
        store accumulates reports without bound, so "read every payload and
        throw the reviews away" is the one call that has to stay cheap.
        """
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

    def list_summaries(self, session_id: str) -> list[ReportSummary]:
        return [ReportSummary.of(report) for report in self.list_for_session(session_id)]

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

    def list_summaries(self, session_id: str) -> list[ReportSummary]:
        return [ReportSummary.of(report) for report in self.list_for_session(session_id)]

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        return []

    def delete(self, report_id: str, session_id: str) -> bool:
        report = self.get(report_id)
        if report is None or report.session_id != session_id:
            return False
        self._client.delete(self._key(report_id))
        self._client.zrem(self._index_key(session_id), report_id)
        return True


class PostgresReportRepository:
    """Durable :class:`ReportRepository` backed by the ``contract_reports`` table.

    Nothing expires here. That is the whole point: the Redis store answers
    "what did I review recently", this one answers "what have I ever
    reviewed", and a report leaves only when its owner deletes it.

    Each call takes a short-lived session from ``session_factory`` rather than
    holding one open. The repository is a process-wide singleton shared by
    every request, and a SQLAlchemy ``Session`` is neither thread-safe nor
    meant to live that long — a single shared one would leak another request's
    failed transaction into this one.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def save(self, report: ContractReviewReport) -> None:
        """Insert the report, or replace the stored copy if it already exists.

        ``merge`` rather than ``add``: overrides and acceptances re-save a
        report that is already in the table, and this is the write path for
        both the first save and every edit after it.
        """
        with self._session() as session:
            session.merge(self._to_row(report))
            session.commit()

    def get(self, report_id: str) -> ContractReviewReport | None:
        with self._session() as session:
            row = session.get(ContractReport, report_id)
            return ContractReviewReport.model_validate(row.payload) if row is not None else None

    def list_for_session(self, session_id: str) -> list[ContractReviewReport]:
        with self._session() as session:
            rows = (
                session.query(ContractReport.payload)
                .filter(ContractReport.session_id == session_id)
                .order_by(ContractReport.created_at.desc())
                .all()
            )
        return [ContractReviewReport.model_validate(row.payload) for row in rows]

    def list_summaries(self, session_id: str) -> list[ReportSummary]:
        """Read the history rows straight out of the denormalized columns.

        The payload column is deliberately not selected: it is the entire
        contract's clause text, and none of it is rendered in a history list.
        """
        with self._session() as session:
            rows = (
                session.query(
                    ContractReport.report_id,
                    ContractReport.contract_id,
                    ContractReport.filename,
                    ContractReport.created_at,
                    ContractReport.overall_risk,
                    ContractReport.summary,
                    ContractReport.clause_count,
                )
                .filter(ContractReport.session_id == session_id)
                .order_by(ContractReport.created_at.desc())
                .all()
            )
        return [
            ReportSummary(
                report_id=row.report_id,
                contract_id=row.contract_id,
                filename=row.filename,
                created_at=_as_utc(row.created_at),
                overall_risk=row.overall_risk,
                summary=row.summary,
                clause_count=row.clause_count,
            )
            for row in rows
        ]

    def purge_expired(self, session_id: str, ttl_seconds: int) -> list[str]:
        """No-op — stored reports do not expire.

        Part of the interface only because ``ReviewService`` sweeps on every
        upload without knowing which backend is wired in.
        """
        return []

    def delete(self, report_id: str, session_id: str) -> bool:
        with self._session() as session:
            deleted = (
                session.query(ContractReport)
                .filter(
                    ContractReport.report_id == report_id,
                    ContractReport.session_id == session_id,
                )
                .delete()
            )
            session.commit()
        return bool(deleted)

    @staticmethod
    def _to_row(report: ContractReviewReport) -> ContractReport:
        return ContractReport(
            report_id=report.report_id,
            session_id=report.session_id,
            contract_id=report.contract_id,
            filename=report.filename,
            created_at=report.created_at,
            updated_at=datetime.now(UTC),
            overall_risk=report.overall_risk.value,
            summary=report.summary.model_dump(),
            clause_count=len(report.reviews),
            # ``mode="json"`` so datetimes land as ISO strings the JSON column
            # can hold and ``model_validate`` reads straight back.
            payload=report.model_dump(mode="json"),
        )


def _as_utc(value: datetime) -> datetime:
    """Attach UTC to a naive timestamp read back from the database.

    Postgres hands back an aware datetime; SQLite (what the tests run on) drops
    the zone. Callers compare and serialize these, so they must not depend on
    which backend produced them.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
