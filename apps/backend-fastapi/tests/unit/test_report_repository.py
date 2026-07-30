"""The report stores, and the session index the Redis one keeps.

The three backends do genuinely different things to answer the same two
questions - the in-memory store filters a dict, Redis reads a sorted set it has
to maintain itself, Postgres runs a query - so all three are tested against one
set of expectations here. The tests below the shared block cover what is unique
to a backend: Redis' index housekeeping, and the fact that Postgres rows
outlive the process that wrote them.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, ContractReport
from app.repositories.report import (
    InMemoryReportRepository,
    PostgresReportRepository,
    RedisReportRepository,
)
from app.schemas import (
    Clause,
    ClauseReview,
    ContractReviewReport,
    RiskLevel,
    RiskSummary,
    Span,
)


class FakeRedis:
    """Just enough Redis for the report repository.

    TTLs are recorded rather than enforced - nothing here waits an hour for a
    key to expire, so tests that need an expired report delete it outright with
    :meth:`drop`, which is what Redis would have done on its own.
    """

    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.ttls: dict[str, int] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.strings[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        self.zsets.setdefault(key, {}).update(mapping)

    def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        members = sorted(self.zsets.get(key, {}).items(), key=lambda kv: kv[1], reverse=True)
        ids = [member for member, _ in members]
        return ids[start:] if end == -1 else ids[start : end + 1]

    def zrem(self, key: str, *members: str) -> None:
        for member in members:
            self.zsets.get(key, {}).pop(member, None)

    def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = seconds

    def drop(self, key: str) -> None:
        """Simulate a key reaching the end of its TTL."""
        self.strings.pop(key, None)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self.strings.pop(key, None)
            self.zsets.pop(key, None)
            self.ttls.pop(key, None)


def make_report(
    report_id: str,
    session_id: str = "user-1",
    *,
    age_seconds: int = 0,
    clauses: int = 0,
):
    return ContractReviewReport(
        report_id=report_id,
        contract_id=f"contract-{report_id}",
        session_id=session_id,
        filename=f"{report_id}.docx",
        created_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
        overall_risk=RiskLevel.HIGH if clauses else RiskLevel.UNKNOWN,
        summary=RiskSummary(high=clauses),
        reviews=[
            ClauseReview(
                clause=Clause(
                    id=f"clause-{i}", text="Unlimited liability.", span=Span(start=0, end=20)
                ),
                risk_level=RiskLevel.HIGH,
            )
            for i in range(1, clauses + 1)
        ],
    )


def sqlite_report_repo() -> tuple[PostgresReportRepository, object]:
    """A Postgres repository pointed at a throwaway SQLite database.

    Only ``contract_reports`` is created: the other tables include
    ``playbook_embeddings``, whose pgvector column type SQLite has no
    equivalent for.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[ContractReport.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return PostgresReportRepository(factory), engine


@pytest.fixture(params=["memory", "redis", "postgres"])
def repo(request: pytest.FixtureRequest) -> Iterator[object]:
    if request.param == "memory":
        yield InMemoryReportRepository()
    elif request.param == "redis":
        yield RedisReportRepository(FakeRedis(), ttl_seconds=3600)
    else:
        repository, engine = sqlite_report_repo()
        yield repository
        engine.dispose()


def test_list_for_session_returns_newest_first(repo) -> None:
    repo.save(make_report("old", age_seconds=120))
    repo.save(make_report("new"))

    assert [r.report_id for r in repo.list_for_session("user-1")] == ["new", "old"]


def test_list_for_session_ignores_other_sessions(repo) -> None:
    repo.save(make_report("mine", "user-1"))
    repo.save(make_report("theirs", "user-2"))

    assert [r.report_id for r in repo.list_for_session("user-1")] == ["mine"]


def test_list_for_session_is_empty_for_an_unknown_session(repo) -> None:
    assert repo.list_for_session("nobody") == []


def test_saving_the_same_report_twice_lists_it_once(repo) -> None:
    """An override re-saves the report; history must not gain a duplicate row."""
    report = make_report("r1")
    repo.save(report)
    report.filename = "renamed.docx"
    repo.save(report)

    rows = repo.list_for_session("user-1")
    assert len(rows) == 1
    assert rows[0].filename == "renamed.docx"


def test_list_summaries_returns_history_rows_newest_first(repo) -> None:
    repo.save(make_report("old", age_seconds=120, clauses=1))
    repo.save(make_report("new", clauses=3))

    rows = repo.list_summaries("user-1")

    assert [row.report_id for row in rows] == ["new", "old"]
    assert rows[0].filename == "new.docx"
    assert rows[0].clause_count == 3
    assert rows[0].overall_risk is RiskLevel.HIGH
    assert rows[0].summary.high == 3


def test_list_summaries_ignores_other_sessions(repo) -> None:
    repo.save(make_report("mine", "user-1"))
    repo.save(make_report("theirs", "user-2"))

    assert [row.report_id for row in repo.list_summaries("user-1")] == ["mine"]


def test_list_summaries_follows_a_re_saved_report(repo) -> None:
    """An override re-scores the report; the history row has to move with it."""
    report = make_report("r1", clauses=2)
    repo.save(report)
    report.summary = RiskSummary(high=1, low=1)
    report.overall_risk = RiskLevel.MEDIUM
    repo.save(report)

    row = repo.list_summaries("user-1")[0]

    assert row.overall_risk is RiskLevel.MEDIUM
    assert row.summary.low == 1


# --- postgres-only ------------------------------------------------------------


def test_postgres_reports_outlive_the_repository_that_wrote_them() -> None:
    """The point of the table: a restart is not a reason to lose a review."""
    repo, engine = sqlite_report_repo()
    try:
        repo.save(make_report("r1", clauses=1))

        reopened = PostgresReportRepository(sessionmaker(bind=engine, autoflush=False))
        stored = reopened.get("r1")

        assert stored is not None
        assert stored.filename == "r1.docx"
        assert len(stored.reviews) == 1
    finally:
        engine.dispose()


def test_postgres_reports_never_expire() -> None:
    repo, engine = sqlite_report_repo()
    try:
        repo.save(make_report("ancient", age_seconds=60 * 60 * 24 * 365))

        assert repo.purge_expired("user-1", ttl_seconds=1) == []
        assert repo.get("ancient") is not None
    finally:
        engine.dispose()


def test_a_report_stored_before_the_newer_fields_still_loads() -> None:
    """Stored reports outlive the schema now, so old payloads must still open.

    ``accepted`` and ``metadata`` were added after reports started being kept
    permanently. A row written before that has neither, and the reviewer who
    saved it should get their report back rather than a validation error.
    """
    repo, engine = sqlite_report_repo()
    try:
        legacy_payload = {
            "report_id": "old",
            "contract_id": "c1",
            "session_id": "user-1",
            "filename": "old.docx",
            "created_at": "2026-07-20T10:00:00Z",
            "overall_risk": "high",
            "summary": {"high": 1, "medium": 0, "low": 0, "unknown": 0},
            "reviews": [
                {
                    "clause": {
                        "id": "clause-1",
                        "text": "Unlimited liability.",
                        "span": {"start": 0, "end": 20, "page": 1},
                        "clause_type": "limitation_of_liability",
                        "heading": None,
                    },
                    "risk_level": "high",
                    "rationale": "No cap.",
                    "citations": [],
                    "suggested_fallback": None,
                    "verified": True,
                }
            ],
            "disclaimer": "not legal advice",
        }
        with sessionmaker(bind=engine, autoflush=False)() as session:
            session.add(
                ContractReport(
                    report_id="old",
                    session_id="user-1",
                    contract_id="c1",
                    filename="old.docx",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    overall_risk="high",
                    summary=legacy_payload["summary"],
                    clause_count=1,
                    payload=legacy_payload,
                )
            )
            session.commit()

        stored = repo.get("old")

        assert stored is not None
        assert stored.reviews[0].accepted is False
        assert stored.metadata.is_empty()
    finally:
        engine.dispose()


def test_postgres_summary_timestamps_are_timezone_aware() -> None:
    """SQLite drops the zone on the way back; callers must not have to care."""
    repo, engine = sqlite_report_repo()
    try:
        repo.save(make_report("r1"))

        assert repo.list_summaries("user-1")[0].created_at.tzinfo is not None
    finally:
        engine.dispose()


# --- redis-only ---------------------------------------------------------------


def test_redis_index_drops_entries_whose_report_expired() -> None:
    client = FakeRedis()
    repo = RedisReportRepository(client, ttl_seconds=3600)
    repo.save(make_report("gone"))
    repo.save(make_report("alive"))

    client.drop("report:gone")

    assert [r.report_id for r in repo.list_for_session("user-1")] == ["alive"]
    # And the dangling id is swept, not re-checked on every later read.
    assert client.zrevrange("session:user-1:reports", 0, -1) == ["alive"]


def test_redis_index_ttl_is_refreshed_on_every_save() -> None:
    """Otherwise the index would expire while its newest report is still live."""
    client = FakeRedis()
    repo = RedisReportRepository(client, ttl_seconds=3600)

    repo.save(make_report("r1"))
    client.ttls["session:user-1:reports"] = 5  # time has passed
    repo.save(make_report("r2"))

    assert client.ttls["session:user-1:reports"] == 3600


def test_delete_report_removes_report(repo) -> None:
    repo.save(make_report("r1", "user-1"))
    repo.save(make_report("r2", "user-1"))

    assert repo.delete("r1", "user-1") is True
    assert [r.report_id for r in repo.list_for_session("user-1")] == ["r2"]
    assert repo.get("r1") is None


def test_delete_report_fails_for_wrong_session(repo) -> None:
    repo.save(make_report("r1", "user-1"))

    assert repo.delete("r1", "user-2") is False
    assert repo.get("r1") is not None
