"""Rescore matching saved contracts without model calls and compare latency.

Run from apps/backend-fastapi. Partial runs are explicitly identified; they
cannot establish completion of the requested ten-contract comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.schemas import ContractReviewReport
from app.services.evaluation import run_eval


def compare(baseline: Path, candidate: Path, gold: Path) -> dict:
    old = json.loads((baseline / "results.json").read_text())
    new = json.loads((candidate / "results.json").read_text())
    if hashlib.sha256(gold.read_bytes()).hexdigest() != new["gold_sha256"]:
        raise ValueError("Current gold file differs from saved evaluation")
    if old["gold_sha256"] != new["gold_sha256"]:
        raise ValueError("Gold sets differ")
    if old["playbook_sha256"] != new["playbook_sha256"]:
        raise ValueError("Playbooks differ")
    for directory in (baseline, candidate):
        if (
            hashlib.sha256((directory / "playbook.json").read_bytes()).hexdigest()
            != new["playbook_sha256"]
        ):
            raise ValueError("Saved playbook differs from manifest")
    old_rows = {r["contract_id"]: r for r in old["completed_contracts"]}
    new_rows = {r["contract_id"]: r for r in new["completed_contracts"]}
    ids = set(old_rows) & set(new_rows)
    if not ids:
        raise ValueError("No matching completed contracts")
    for contract_id in ids:
        if old["fixture_sha256"][contract_id] != new["fixture_sha256"][contract_id]:
            raise ValueError(f"Fixture differs: {contract_id}")
        fixture = gold.resolve().parent.parent / "contracts" / f"{contract_id}.txt"
        if hashlib.sha256(fixture.read_bytes()).hexdigest() != new["fixture_sha256"][contract_id]:
            raise ValueError(f"Current fixture differs: {contract_id}")

    class SavedReports:
        def __init__(self, directory):
            self.directory = directory

        def review(self, document, *, contract_id, session_id):
            return ContractReviewReport.model_validate_json(
                (self.directory / f"{contract_id}.json").read_text()
            )

    positions = {
        p["id"] for p in json.loads((candidate / "playbook.json").read_text())["positions"]
    }
    metrics = {}
    for label, directory, rows in [
        ("baseline", baseline, old_rows),
        ("candidate", candidate, new_rows),
    ]:
        scored = run_eval(
            gold,
            orchestrator=SavedReports(directory),
            known_position_ids=positions,
            contract_ids=ids,
        )
        metrics[label] = {
            "metrics": scored.model_dump(mode="json"),
            "elapsed_seconds": sum(rows[key]["elapsed_seconds"] for key in ids),
            "clauses": sum(rows[key]["predicted_clauses"] for key in ids),
            "failed_clauses": sum(rows[key]["failed_clauses"] for key in ids),
            "unknown_risk_clauses": sum(rows[key]["unknown_risk_clauses"] for key in ids),
            "verified_clauses": sum(rows[key]["verified_clauses"] for key in ids),
        }
    baseline_seconds = metrics["baseline"]["elapsed_seconds"]
    candidate_seconds = metrics["candidate"]["elapsed_seconds"]
    complete = (
        old["status"] == new["status"] == "complete"
        and set(old["fixture_sha256"]) == set(new["fixture_sha256"]) == ids
    )
    return {
        "complete_comparison": complete,
        "matching_contracts": sorted(ids),
        "missing_baseline": sorted(set(new["fixture_sha256"]) - set(old_rows)),
        "missing_candidate": sorted(set(new["fixture_sha256"]) - set(new_rows)),
        "baseline_config": old["config"],
        "candidate_config": new["config"],
        **metrics,
        "speedup": baseline_seconds / candidate_seconds if candidate_seconds else None,
        "classification_accuracy_delta": (
            metrics["candidate"]["metrics"]["classification_accuracy"]
            - metrics["baseline"]["metrics"]["classification_accuracy"]
        ),
        "risk_accuracy_delta": (
            metrics["candidate"]["metrics"]["risk_accuracy"]
            - metrics["baseline"]["metrics"]["risk_accuracy"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--gold", type=Path, default=Path("data/gold/annotations.jsonl"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, args.gold)
    formatted = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(formatted)
    print(formatted)


if __name__ == "__main__":
    main()
