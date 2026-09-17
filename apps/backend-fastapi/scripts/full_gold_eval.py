"""Run all gold fixtures with saved reports, provenance, and per-contract progress.

Run from apps/backend-fastapi. Uses real configured providers and API quota.
The output contains public CUAD contract text and generated reviews, no credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import get_settings


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model")
    parser.add_argument("--database-port", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--limit", type=int, help="Evaluate the first N gold contracts")
    parser.add_argument("--openrouter-providers", nargs="+")
    args = parser.parse_args()
    settings = get_settings()
    if args.model:
        settings.llm_model = args.model
    if args.openrouter_providers:
        settings.llm_openrouter_providers = args.openrouter_providers
    if args.database_port:
        settings.database_url = (
            make_url(settings.database_url)
            .set(host="127.0.0.1", port=args.database_port)
            .render_as_string(hide_password=False)
        )
    if args.concurrency is not None:
        if args.concurrency < 1:
            parser.error("--concurrency must be positive")
        settings.review_concurrency = args.concurrency

    # Infrastructure imports must follow the process-local settings overrides.
    from app.dependencies import get_known_positions, get_llm_client, get_orchestrator
    from app.parsers import ParsedDocument, TextSpan, normalize
    from app.schemas import Span
    from app.services.evaluation import format_report, load_gold, run_eval, segmentation_f1

    logging.basicConfig(level=logging.WARNING)
    output = Path(args.output).resolve()
    if (output / "results.json").exists():
        raise RuntimeError("Output already contains results; use a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    gold_path = Path("data/gold/annotations.jsonl")
    records = load_gold(gold_path)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        records = records[: args.limit]
    fixtures = {
        r["contract_id"]: Path("data/contracts") / f"{r['contract_id']}.txt" for r in records
    }
    missing = [str(path) for path in fixtures.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing gold fixtures: {missing}")
    positions = get_known_positions()
    position_data = [positions[key].model_dump(mode="json") for key in sorted(positions)]
    save(output / "playbook.json", {"positions": position_data})
    llm = get_llm_client()
    orchestrator = get_orchestrator()
    import app

    source_root = Path(app.__file__).resolve().parent
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "process_id": os.getpid(),
        "source_sha256": {
            str(path.relative_to(source_root)): digest(path)
            for path in sorted(source_root.rglob("*"))
            if path.suffix in {".py", ".jinja"}
        },
        "runner_sha256": digest(Path(__file__)),
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "gold_sha256": digest(gold_path),
        "fixture_sha256": {key: digest(path) for key, path in fixtures.items()},
        "playbook_sha256": digest(output / "playbook.json"),
        "config": {
            "provider": settings.llm_provider,
            "model": llm.model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "embedding_dim": settings.embedding_dim,
            "enable_judge": settings.enable_judge,
            "enable_hybrid_retrieval": settings.enable_hybrid_retrieval,
            "enable_embedding_cache": settings.enable_embedding_cache,
            "thinking": settings.llm_thinking,
            "concurrency": settings.review_concurrency,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_attempts": settings.llm_max_attempts,
            "judge_prompt_version": orchestrator.judge.prompt_version,
            "scorer_prompt_version": orchestrator.risk_scorer.prompt_version,
            "classifier_prompt_version": orchestrator.classifier.prompt_version,
            "openrouter_providers": getattr(settings, "llm_openrouter_providers", []),
        },
        "expected": {
            "contracts": len(records),
            "clauses": sum(len(r["clauses"]) for r in records),
            "labelled_clauses": sum("clause_type" in c for r in records for c in r["clauses"]),
        },
        "completed_contracts": [],
        "comparison": {
            "iteration_2": "Awaiting source baseline; not identified in repository.",
            "prd_thresholds": "Awaiting PRD; repository regression gates are separate.",
        },
    }
    save(output / "results.json", manifest)
    started = time.perf_counter()

    class CheckpointOrchestrator:
        def __init__(self):
            self.reports = {}

        def review(self, document, *, contract_id, session_id):
            if contract_id in self.reports:
                return self.reports[contract_id]
            index = len(self.reports) + 1
            print(f"[{index}/{len(records)}] START {contract_id}", flush=True)
            tick = time.perf_counter()
            report = orchestrator.review(document, contract_id=contract_id, session_id=session_id)
            self.reports[contract_id] = report
            save(output / f"{contract_id}.json", report.model_dump(mode="json"))
            gold_record = next(r for r in records if r["contract_id"] == contract_id)
            citations = [c for review in report.reviews for c in review.citations]
            row = {
                "contract_id": contract_id,
                "elapsed_seconds": time.perf_counter() - tick,
                "gold_clauses": len(gold_record["clauses"]),
                "predicted_clauses": len(report.reviews),
                "labelled_clauses": sum("clause_type" in c for c in gold_record["clauses"]),
                "segmentation_f1": segmentation_f1(
                    [r.clause.span for r in report.reviews],
                    [Span(**c["span"]) for c in gold_record["clauses"]],
                ),
                "verified_clauses": sum(r.verified for r in report.reviews),
                "unknown_risk_clauses": sum(
                    r.risk_level.value == "unknown" for r in report.reviews
                ),
                "failed_clauses": sum(
                    r.rationale
                    == "Automated review failed for this clause; manual review required."
                    for r in report.reviews
                ),
                "citations": len(citations),
                "valid_citations": sum(c.playbook_position_id in positions for c in citations),
            }
            manifest["completed_contracts"].append(row)
            manifest["elapsed_seconds"] = time.perf_counter() - started
            save(output / "results.json", manifest)
            print(f"[{index}/{len(records)}] DONE {json.dumps(row)}", flush=True)
            return report

    checkpoint = CheckpointOrchestrator()
    try:
        # Complete the shortest fixture first to establish live pipeline health.
        smoke = min(records, key=lambda r: len(r["clauses"]))
        smoke_text = normalize(fixtures[smoke["contract_id"]].read_text())
        smoke_doc = ParsedDocument(
            text=smoke_text,
            spans=[TextSpan(start=0, end=len(smoke_text), page=1)],
            page_map={1: (0, len(smoke_text))},
        )
        checkpoint.review(smoke_doc, contract_id=smoke["contract_id"], session_id="eval")
        smoke_result = manifest["completed_contracts"][-1]
        if smoke_result["failed_clauses"] == smoke_result["predicted_clauses"]:
            raise RuntimeError("Every smoke-contract clause failed; refusing remaining API calls")
        metrics = run_eval(
            gold_path,
            orchestrator=checkpoint,
            known_position_ids=set(positions),
            contract_ids=set(fixtures),
        )
        manifest["metrics"] = metrics.model_dump(mode="json")
        rows = manifest["completed_contracts"]
        manifest["quality"] = {
            "reviewed_clauses": sum(r["predicted_clauses"] for r in rows),
            "verified_clauses": sum(r["verified_clauses"] for r in rows),
            "failed_clauses": sum(r["failed_clauses"] for r in rows),
            "unknown_risk_clauses": sum(r["unknown_risk_clauses"] for r in rows),
            "citations": sum(r["citations"] for r in rows),
            "valid_citations": sum(r["valid_citations"] for r in rows),
            "all_contracts_segmentation_f1": {r["contract_id"]: r["segmentation_f1"] for r in rows},
        }
        manifest["repository_regression_gates"] = {
            "source": "tests/eval/test_regression.py (not verified PRD thresholds)",
            "segmentation_f1": {"minimum": 0.95, "passed": metrics.segmentation_f1 >= 0.95},
            "citation_validity": {"minimum": 1.0, "passed": metrics.citation_validity >= 1.0},
        }
        manifest["token_usage"] = {
            "input_tokens": llm.usage.input_tokens,
            "output_tokens": llm.usage.output_tokens,
            "cache_read_input_tokens": llm.usage.cache_read_input_tokens,
        }
        manifest["status"] = "complete"
        (output / "metrics.txt").write_text(format_report(metrics) + "\n")
        print(format_report(metrics), flush=True)
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "error"
        manifest["error_type"] = type(exc).__name__
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest["elapsed_seconds"] = time.perf_counter() - started
        save(output / "results.json", manifest)


if __name__ == "__main__":
    main()
