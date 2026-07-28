"""The report stores, and the session index the Redis one keeps.

``list_for_session`` is the only place the two backends do genuinely different
things - the in-memory store filters a dict, Redis reads a sorted set it has to
maintain itself - so both are tested against the same expectations here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.report import InMemoryReportRepository, RedisReportRepository
from app.schemas import ContractReviewReport


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



def make_report(report_id: str, session_id: str = "user-1", *, age_seconds: int = 0):
    return ContractReviewReport(
        report_id=report_id,
        contract_id=f"contract-{report_id}",
        session_id=session_id,
        filename=f"{report_id}.docx",
        created_at=datetime.now(UTC) - timedelta(seconds=age_seconds),
    )


@pytest.fixture(params=["memory", "redis"])
def repo(request: pytest.FixtureRequest):
    if request.param == "memory":
        return InMemoryReportRepository()
    return RedisReportRepository(FakeRedis(), ttl_seconds=3600)


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
