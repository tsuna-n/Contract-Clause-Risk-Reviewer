"""Background jobs return promptly, isolate users, and retain terminal results."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.errors import InvalidInputError, NotFoundError
from app.schemas import EvalMetrics, EvalRequest
from app.services import evaluation
from app.services.eval_jobs import ACTIVE_KEY, EvalJobs


class MemoryStore:
    def __init__(self):
        self.values = {}
        self.completed = threading.Event()

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if key.startswith("evaluation:job:") and json.loads(value)["status"] != "running":
            self.completed.set()
        return True

    def eval(self, script, count, key, job_id, *args):
        if self.values.get(key) == job_id and "'del'" in script:
            del self.values[key]


class HeldService:
    def __init__(self, error=None):
        self.release = threading.Event()
        self.entered = threading.Event()
        self.error = error
        self.calls = 0

    def run(self, request, *, on_progress):
        self.calls += 1
        on_progress({"contract_id": "sample", "total_clauses": 8, "completed_clauses": 3})
        self.entered.set()
        assert self.release.wait(2)
        if self.error:
            raise self.error
        on_progress({"completed_contracts": 1, "completed_clauses": 8})
        return EvalMetrics(classification_accuracy=0.75)


@pytest.fixture()
def jobs(tmp_path: Path, monkeypatch):
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "annotations.jsonl").write_text(json.dumps({"contract_id": "sample", "clauses": []}))
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "sample.txt").write_text("1. Sample. Contract text.")
    monkeypatch.setattr(evaluation, "GOLD_SET_ROOT", gold)
    store = MemoryStore()
    return EvalJobs(store), store, EvalRequest(gold_set_path=str(gold / "annotations.jsonl"))


def test_job_returns_before_model_finishes_and_same_owner_resumes(jobs):
    manager, store, request = jobs
    service = HeldService()
    try:
        job = manager.start(request, "alice", service)
        assert service.entered.wait(1)
        current = manager.get(job.job_id, "alice")
        assert current.status == "running"
        assert current.completed_clauses == 3
        assert current.total_clauses == 8
        assert manager.start(request, "alice", service).job_id == job.job_id
        assert service.calls == 1
        with pytest.raises(NotFoundError):
            manager.get(job.job_id, "bob")
        with pytest.raises(HTTPException) as exc:
            manager.start(request, "bob", service)
        assert exc.value.status_code == 409
    finally:
        service.release.set()
    assert store.completed.wait(1)
    result = manager.get(job.job_id, "alice")
    assert result.status == "completed"
    assert result.metrics.classification_accuracy == 0.75
    assert result.completed_contracts == 1


def test_job_failure_is_saved_without_leaking_exception_details(jobs):
    manager, store, request = jobs
    service = HeldService(RuntimeError("secret api key or provider details"))
    service.release.set()
    job = manager.start(request, "alice", service)
    assert store.completed.wait(1)
    result = manager.get(job.job_id, "alice")
    assert result.status == "failed"
    assert "secret" not in result.error


def test_missing_fixture_fails_before_scheduling(jobs):
    manager, _, request = jobs
    Path(request.gold_set_path).write_text(json.dumps({"contract_id": "missing"}))
    service = HeldService()
    with pytest.raises(InvalidInputError, match="fixture missing"):
        manager.start(request, "alice", service)
    assert service.calls == 0


def test_stopped_worker_is_reported_instead_of_polling_forever(jobs):
    manager, store, request = jobs
    service = HeldService()
    try:
        job = manager.start(request, "alice", service)
        assert service.entered.wait(1)
        del store.values[ACTIVE_KEY]
        result = manager.get(job.job_id, "alice")
        assert result.status == "failed"
        assert "worker stopped" in result.error
    finally:
        service.release.set()
    assert store.completed.wait(1)
