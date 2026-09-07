"""Measure real HTTP features using a disposable PostgreSQL database.

Run from apps/backend-fastapi. Calls the configured paid model when --live is
provided. Copies only playbook vectors from the existing DB, never user reports.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import get_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--output", default="../../reports/feature-benchmark.json")
    args = parser.parse_args()
    settings = get_settings()
    original_model = settings.llm_model
    source_url = make_url(settings.database_url)
    bench_name = f"contract_bench_{uuid.uuid4().hex[:12]}"
    admin = create_engine(source_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        positions = [
            dict(row)
            for row in conn.execute(
                text(
                    "SELECT id, clause_type, title, preferred_language, fallback_language, "
                    "risk_if_absent, tags, embedding::text AS embedding FROM playbook_embeddings"
                )
            ).mappings()
        ]
        conn.execute(text(f"CREATE DATABASE {bench_name}"))
    test_url = source_url.set(database=bench_name).render_as_string(hide_password=False)
    os.environ.update(DATABASE_URL=test_url, APP_ENV="development", ENABLE_DEV_LOGIN="true")
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    get_settings.cache_clear()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results = {
        "started_at": datetime.now(UTC).isoformat(),
        "original_model": original_model,
        "tested_model": get_settings().llm_model,
        "live": args.live,
        "transport": "HTTP loopback, uvicorn, real Postgres/Redis",
        "playbook_count": len(positions),
        "measurements": [],
        "stages": {},
        "notes": [
            "OAuth consent and Google callback require a real browser login; not timed.",
            "Database is disposable; playbook vectors copied from existing database.",
            "Review latency uses one sample per file type, not a throughput benchmark.",
        ],
    }
    server = None
    worker = None
    engine = None
    temp_gold = None
    lock = threading.Lock()

    def save():
        with lock:
            output.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    def measure(name, fn, repeats=1, check=None):
        elapsed = []
        failures = []
        last = None
        for _ in range(repeats):
            start = time.perf_counter()
            try:
                last = fn()
                if check:
                    check(last)
            except Exception as exc:
                failures.append(type(exc).__name__ + ": " + str(exc)[:200])
            elapsed.append((time.perf_counter() - start) * 1000)
        ordered = sorted(elapsed)
        row = {
            "feature": name,
            "n": repeats,
            "median_ms": statistics.median(elapsed),
            "min_ms": ordered[0],
            "max_ms": ordered[-1],
            "samples_ms": elapsed,
            "status": "passed" if not failures else "failed",
            "errors": failures,
        }
        results["measurements"].append(row)
        save()
        print(json.dumps({k: v for k, v in row.items() if k != "samples_ms"}), flush=True)
        return last

    def status(expected):
        def check(response):
            if response.status_code != expected:
                raise AssertionError(f"Expected HTTP {expected}; got {response.status_code}")

        return check

    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        from app.database import engine
        from app.models import PlaybookEmbedding

        with engine.begin() as conn:
            for row in positions:
                row["embedding"] = json.loads(row["embedding"])
            conn.execute(PlaybookEmbedding.__table__.insert(), positions)

        import uvicorn

        from app.dependencies import get_orchestrator
        from app.main import create_app
        from app.parsers import PARSERS

        app = create_app()
        orchestrator = get_orchestrator()
        for stage in (
            "segmenter",
            "classifier",
            "matcher",
            "risk_scorer",
            "judge",
            "metadata_extractor",
        ):
            agent = getattr(orchestrator, stage)
            if agent is None:
                continue
            original = agent.run

            def traced(*a, _fn=original, _stage=stage, **kw):
                start = time.perf_counter()
                try:
                    return _fn(*a, **kw)
                finally:
                    with lock:
                        results["stages"].setdefault(_stage, []).append(
                            (time.perf_counter() - start) * 1000
                        )

            agent.run = traced

        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=18000, log_level="error", access_log=False)
        )
        worker = threading.Thread(target=server.run, daemon=True)
        worker.start()
        deadline = time.monotonic() + 15
        while not server.started:
            if not worker.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Benchmark HTTP server did not start")
            time.sleep(0.05)
        with httpx.Client(base_url="http://127.0.0.1:18000", timeout=900) as client:
            measure("Health", lambda: client.get("/health"), 10, status(200))
            measure("Database readiness", lambda: client.get("/health/db"), 10, status(200))
            login = measure(
                "Development login (DB + JWT, not Google consent)",
                lambda: client.get(
                    "/auth/dev-login", params={"email": "benchmark@example.invalid"}
                ),
                10,
                status(307),
            )
            token = parse_qs(urlsplit(login.headers["location"]).query)["token"][0]
            client.headers["Authorization"] = f"Bearer {token}"
            measure("Current user", lambda: client.get("/auth/me"), 10, status(200))
            measure(
                "Google OAuth redirect only",
                lambda: client.get("/auth/google/login"),
                1,
                status(302),
            )
            measure(
                "Playbook list (36 positions)", lambda: client.get("/playbook"), 10, status(200)
            )
            measure(
                "Playbook filter",
                lambda: client.get("/playbook?clause_type=confidentiality"),
                10,
                status(200),
            )
            measure(
                "Playbook detail",
                lambda: client.get(f"/playbook/{positions[0]['id']}"),
                10,
                status(200),
            )
            if args.live:
                measure(
                    "Semantic search first request",
                    lambda: client.get(
                        "/playbook/search",
                        params={"q": "Unlimited liability benchmark query", "top_k": 5},
                    ),
                    1,
                    status(200),
                )
                measure(
                    "Semantic search repeated (embedding cache)",
                    lambda: client.get(
                        "/playbook/search",
                        params={"q": "Unlimited liability benchmark query", "top_k": 5},
                    ),
                    10,
                    status(200),
                )
                payload = {
                    "id": "benchmark-position",
                    "clause_type": "confidentiality",
                    "title": "Benchmark confidentiality",
                    "preferred_language": (
                        "Confidential information shall be protected for three years."
                    ),
                    "fallback_language": (
                        "Confidential information shall be protected for one year."
                    ),
                    "risk_if_absent": "medium",
                    "tags": ["benchmark"],
                }
                measure(
                    "Playbook create with embedding",
                    lambda: client.post("/playbook", json=payload),
                    1,
                    status(201),
                )
                measure(
                    "Playbook update with embedding",
                    lambda: client.put(
                        "/playbook/benchmark-position",
                        json={"title": "Updated benchmark confidentiality"},
                    ),
                    1,
                    status(200),
                )
                with engine.connect() as conn:
                    vector = conn.execute(
                        text(
                            "SELECT embedding::text FROM playbook_embeddings "
                            "WHERE id='benchmark-position'"
                        )
                    ).scalar()
                    results["playbook_embedding_nonzero"] = bool(vector and any(json.loads(vector)))
                measure(
                    "Playbook delete",
                    lambda: client.delete("/playbook/benchmark-position"),
                    1,
                    status(204),
                )

            import fitz
            from docx import Document

            thai = Path("data/samples/thai-nda-short.txt").read_bytes()
            english = [
                "1. Confidentiality. Information must be kept confidential forever.",
                "2. Liability. The supplier has unlimited liability for all damages.",
                "3. Termination. Either party may terminate with 30 days written notice.",
            ]
            doc = Document()
            for line in english:
                doc.add_paragraph(line)
            buf = BytesIO()
            doc.save(buf)
            with fitz.open() as pdf:
                page = pdf.new_page()
                page.insert_text((50, 60), "\n\n".join(english), fontsize=10)
                pdf_data = pdf.write()
            files = [
                ("nda.txt", thai),
                ("contract.docx", buf.getvalue()),
                ("contract.pdf", pdf_data),
            ]
            for filename, data in files:
                measure(
                    f"Parse {filename}",
                    lambda d=data, n=filename: PARSERS[n.rsplit(".", 1)[1]](d),
                    10,
                )
            measure(
                "Reject empty text",
                lambda: client.post("/contracts/review", files={"file": ("empty.txt", b"")}),
                3,
                status(422),
            )
            measure(
                "Reject unsupported file",
                lambda: client.post("/contracts/review", files={"file": ("x.exe", b"bad")}),
                3,
                status(422),
            )
            report_ids = []
            if args.live:
                for filename, data in files:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            lambda n=filename, d=data: measure(
                                f"Upload + AI review {n}",
                                lambda: client.post("/contracts/review", files={"file": (n, d)}),
                                1,
                                status(200),
                            )
                        )
                        time.sleep(0.2)
                        measure(
                            f"Health during {filename} review",
                            lambda: client.get("/health"),
                            5,
                            status(200),
                        )
                        response = future.result()
                    if response is not None and response.status_code == 200:
                        report = response.json()
                        report_ids.append(report["report_id"])
                        quality = {
                            "filename": filename,
                            "clauses": len(report["reviews"]),
                            "unknown": sum(r["risk_level"] == "unknown" for r in report["reviews"]),
                            "provider_failures": sum(
                                "Automated review failed" in r["rationale"]
                                for r in report["reviews"]
                            ),
                            "verified": sum(r["verified"] for r in report["reviews"]),
                            "citations": sum(len(r["citations"]) for r in report["reviews"]),
                        }
                        results.setdefault("reviews", []).append(quality)
                        print(json.dumps(quality), flush=True)
                if report_ids:
                    rid = report_ids[0]
                    measure(
                        "History list (3 reports)",
                        lambda: client.get("/contracts"),
                        10,
                        status(200),
                    )
                    report = measure(
                        "Open report", lambda: client.get(f"/contracts/{rid}"), 10, status(200)
                    ).json()
                    cid = report["reviews"][0]["clause"]["id"]

                    def acceptance(accepted):
                        response = client.post(
                            f"/contracts/{rid}/accept",
                            json={"clause_id": cid, "accepted": accepted},
                        )
                        status(200)(response)
                        assert response.json()["reviews"][0]["accepted"] is accepted
                        return response

                    measure("Accept clause", lambda: acceptance(True), 5)
                    measure("Withdraw acceptance", lambda: acceptance(False), 5)

                    def override():
                        response = client.post(
                            f"/contracts/{rid}/override",
                            json={
                                "clause_id": cid,
                                "new_risk": "high",
                                "reason": "Benchmark test only",
                            },
                        )
                        status(200)(response)
                        assert response.json()["reviews"][0]["risk_level"] == "high"
                        return response

                    measure("Override risk + audit", override, 5)
                    with engine.connect() as conn:
                        results["audit_rows"] = conn.execute(
                            text("SELECT count(*) FROM audit_overrides")
                        ).scalar()
                    for rid in report_ids:
                        measure(
                            "Delete report",
                            lambda r=rid: client.delete(f"/contracts/{r}"),
                            1,
                            status(204),
                        )
                        assert client.get(f"/contracts/{rid}").status_code == 404
                # Shortest existing labeled fixture, preserving its original gold labels.
                records = [
                    json.loads(line)
                    for line in Path("data/gold/annotations.jsonl").read_text().splitlines()
                    if line.strip()
                ]
                record = next(
                    r for r in records if r["contract_id"] == "ticketscominc-sponsorship-agreement"
                )
                temp_gold = Path("data/gold") / f"{bench_name}.jsonl"
                temp_gold.write_text(json.dumps(record) + "\n")
                response = measure(
                    "Evaluate gold contract (8 clauses)",
                    lambda: client.post(
                        "/evaluate", json={"gold_set_path": str(temp_gold), "limit": 1}
                    ),
                    1,
                    status(200),
                )
                if response is not None and response.status_code == 200:
                    results["evaluation"] = response.json()
            measure("Logout", lambda: client.post("/auth/logout"), 10, status(200))
            client.headers.pop("Authorization")
            measure(
                "Reject unauthenticated history", lambda: client.get("/contracts"), 5, status(401)
            )
            # Browser tests may be run against this server while benchmark is active.
        results["completed_at"] = datetime.now(UTC).isoformat()
    finally:
        if server:
            server.should_exit = True
        if worker:
            worker.join(timeout=10)
        if engine:
            engine.dispose()
        if temp_gold:
            temp_gold.unlink(missing_ok=True)
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {bench_name} WITH (FORCE)"))
        admin.dispose()
        results["test_database_removed"] = True
        save()


if __name__ == "__main__":
    main()
