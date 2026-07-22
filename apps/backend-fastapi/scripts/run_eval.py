"""CLI: run the evaluation harness against the gold set.

Usage:
    python -m scripts.run_eval [path/to/annotations.jsonl]
"""

from __future__ import annotations

import sys

from app.api.deps import get_known_positions, get_orchestrator
from app.evaluation.report import format_report
from app.evaluation.runner import run_eval


def main(argv: list[str]) -> int:
    """Run the gold-set evaluation and print the metrics report."""
    path = argv[1] if len(argv) > 1 else "data/gold/annotations.jsonl"
    metrics = run_eval(
        path,
        orchestrator=get_orchestrator(),
        known_position_ids=set(get_known_positions()),
    )
    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
