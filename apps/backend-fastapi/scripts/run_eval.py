"""CLI: run the evaluation harness against the gold set.

Usage:
    python -m scripts.run_eval [path/to/annotations.jsonl]
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    """Run the gold-set evaluation and print the metrics report."""
    from app.evaluation.report import format_report
    from app.evaluation.runner import run_eval

    path = argv[1] if len(argv) > 1 else "data/gold/annotations.jsonl"
    metrics = run_eval(path)
    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
