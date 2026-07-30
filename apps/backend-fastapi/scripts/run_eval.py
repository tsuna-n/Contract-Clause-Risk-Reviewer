"""CLI: run the evaluation harness against the gold set.

Usage:
    python -m scripts.run_eval [path/to/annotations.jsonl] [--limit N]
    python -m scripts.run_eval --contract ticketscominc-sponsorship-agreement

The full set is not a free operation: 12 contracts, 327 clauses, and roughly
four LLM calls per clause. ``--limit`` runs the first N contracts and
``--contract`` runs named ones, so a smoke run can pick a short contract
instead of whichever sits first in the file.
"""

from __future__ import annotations

import argparse
import sys

from app.dependencies import get_known_positions, get_orchestrator
from app.services.evaluation import format_report, run_eval


def main(argv: list[str]) -> int:
    """Run the gold-set evaluation and print the metrics report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "gold_set_path",
        nargs="?",
        default="data/gold/annotations.jsonl",
        help="gold annotations file (default: data/gold/annotations.jsonl)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="only run the first N contracts in the gold set",
    )
    parser.add_argument(
        "--contract",
        action="append",
        dest="contracts",
        default=None,
        metavar="CONTRACT_ID",
        help="only run this contract (repeatable)",
    )
    args = parser.parse_args(argv[1:])

    metrics = run_eval(
        args.gold_set_path,
        orchestrator=get_orchestrator(),
        known_position_ids=set(get_known_positions()),
        limit=args.limit,
        contract_ids=set(args.contracts) if args.contracts else None,
    )
    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
