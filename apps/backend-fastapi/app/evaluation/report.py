"""Evaluation reporting: confusion matrix + per-clause-type breakdown."""

from __future__ import annotations

from app.schemas.eval import EvalMetrics


def confusion_matrix(predicted: list[str], gold: list[str]) -> dict[str, dict[str, int]]:
    """Build a nested ``gold -> predicted -> count`` confusion matrix."""
    matrix: dict[str, dict[str, int]] = {}
    for pred, actual in zip(predicted, gold, strict=True):
        matrix.setdefault(actual, {})
        matrix[actual][pred] = matrix[actual].get(pred, 0) + 1
    return matrix


def format_report(metrics: EvalMetrics) -> str:
    """Render metrics as a human-readable text report.

    TODO: pretty-print aggregate metrics + per-type breakdown.
    """
    raise NotImplementedError
