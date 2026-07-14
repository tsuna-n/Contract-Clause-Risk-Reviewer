"""Evaluation runner: execute the gold set and compute metrics."""

from __future__ import annotations

from pathlib import Path

from app.schemas.eval import EvalMetrics


def load_gold(path: str | Path) -> list[dict]:
    """Load gold annotations from a JSONL file.

    TODO: parse ``data/gold/annotations.jsonl`` into records.
    """
    raise NotImplementedError


def run_eval(gold_path: str | Path, limit: int | None = None) -> EvalMetrics:
    """Run the pipeline over the gold set and return aggregate metrics.

    The eval regression gate requires >= 75% accuracy (see tests/eval).

    TODO: for each gold contract, run the pipeline and score segmentation F1,
    classification accuracy, risk accuracy, and citation validity.
    """
    raise NotImplementedError
