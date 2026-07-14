"""CLI: run the evaluation harness against the gold set.

Usage:
    python -m scripts.run_eval [path/to/annotations.jsonl]
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    """Run the gold-set evaluation and print the metrics report.

    TODO: call ``evaluation.runner.run_eval`` and
    ``evaluation.report.format_report``.
    """
    path = argv[1] if len(argv) > 1 else "data/gold/annotations.jsonl"
    print(f"[run_eval] would evaluate against {path}")
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
