"""Persist evaluation progress in Redis so polling never waits on model calls."""

from __future__ import annotations

import json
import threading
import time
import uuid

import redis
from fastapi import HTTPException

from app.errors import DomainError, InvalidInputError, NotFoundError
from app.logger import get_logger
from app.schemas import EvalJob, EvalRequest
from app.services.evaluation import (
    EvalService,
    _load_contract_text,
    resolve_gold_set_path,
    select_records,
)

logger = get_logger(__name__)
JOB_TTL = 7200
LEASE_TTL = 60
ACTIVE_KEY = "evaluation:active"


class EvalJobs:
    def __init__(self, store: redis.Redis) -> None:
        self.store = store

    def _read(self, job_id: str, owner: str) -> dict:
        raw = self.store.get(f"evaluation:job:{job_id}")
        if raw is None:
            raise NotFoundError("Evaluation expired or was not found. Start a new run.")
        data = json.loads(raw)
        if data["owner"] != owner:
            raise NotFoundError("Evaluation was not found.")
        return data

    def get(self, job_id: str, owner: str) -> EvalJob:
        # Read the lease first: a finishing worker saves its terminal state
        # before releasing it, so this order cannot overwrite a completed job.
        active = self.store.get(ACTIVE_KEY)
        data = self._read(job_id, owner)
        if data["status"] == "running" and active != job_id:
            data.update(
                status="failed",
                finished_at=time.time(),
                error="Evaluation worker stopped. Please start a new run.",
            )
            self.store.set(f"evaluation:job:{job_id}", json.dumps(data), ex=JOB_TTL)
        end = data.get("finished_at", time.time())
        return EvalJob.model_validate({**data, "elapsed_seconds": end - data["started_at"]})

    def start(self, request: EvalRequest, owner: str, service: EvalService) -> EvalJob:
        # Catch fixture mistakes before scheduling any model calls.
        path = resolve_gold_set_path(request.gold_set_path)
        try:
            records = select_records(path, limit=request.limit, order=request.order)
            if not records:
                raise InvalidInputError("The gold set contains no contracts.")
            for record in records:
                if _load_contract_text(path, record["contract_id"]) is None:
                    raise InvalidInputError(f"Contract fixture missing: {record['contract_id']}")
        except (OSError, ValueError, KeyError) as exc:
            raise InvalidInputError(
                "Cannot load the gold set. Check the file and annotations."
            ) from exc

        job_id = uuid.uuid4().hex
        if not self.store.set(ACTIVE_KEY, job_id, nx=True, ex=LEASE_TTL):
            active = self.store.get(ACTIVE_KEY)
            if active:
                try:
                    return self.get(active, owner)
                except NotFoundError:
                    pass
            raise HTTPException(
                409, "An evaluation is already running. Please wait for it to finish."
            )

        data = {
            **EvalJob(job_id=job_id, total_contracts=len(records)).model_dump(),
            "owner": owner,
            "started_at": time.time(),
        }

        def save() -> None:
            self.store.set(f"evaluation:job:{job_id}", json.dumps(data), ex=JOB_TTL)

        def progress(update: dict) -> None:
            data.update(update)
            save()

        stopped = threading.Event()

        def heartbeat() -> None:
            while not stopped.wait(15):
                try:
                    self.store.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then "
                        "return redis.call('expire', KEYS[1], ARGV[2]) end return 0",
                        1,
                        ACTIVE_KEY,
                        job_id,
                        LEASE_TTL,
                    )
                except redis.RedisError:
                    logger.exception("evaluation heartbeat failed")

        def run() -> None:
            threading.Thread(target=heartbeat, daemon=True).start()
            try:
                metrics = service.run(request, on_progress=progress)
                data.update(status="completed", metrics=metrics.model_dump(mode="json"))
            except Exception as exc:
                logger.exception("evaluation %s failed", job_id)
                data.update(
                    status="failed",
                    error=exc.message
                    if isinstance(exc, DomainError)
                    else ("Evaluation failed. Check the backend log and model connection."),
                )
            finally:
                stopped.set()
                data["finished_at"] = time.time()
                try:
                    save()
                finally:
                    self.store.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then "
                        "return redis.call('del', KEYS[1]) end return 0",
                        1,
                        ACTIVE_KEY,
                        job_id,
                    )

        try:
            save()
            threading.Thread(target=run, name=f"eval-{job_id}", daemon=True).start()
        except Exception:
            stopped.set()
            self.store.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then "
                "return redis.call('del', KEYS[1]) end return 0",
                1,
                ACTIVE_KEY,
                job_id,
            )
            raise
        return self.get(job_id, owner)
