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
    """Render metrics as a human-readable text report."""
    lines = [
        "Evaluation report",
        "==================",
        f"segmentation_f1:          {metrics.segmentation_f1:.2%}",
        f"classification_accuracy:  {metrics.classification_accuracy:.2%}",
        f"risk_accuracy:            {metrics.risk_accuracy:.2%}",
        f"citation_validity:        {metrics.citation_validity:.2%}",
    ]
    if metrics.per_type:
        lines.append("")
        lines.append("Per clause type:")
        for row in metrics.per_type:
            lines.append(f"  {row.clause_type:<28} n={row.support:<4} acc={row.accuracy:.2%}")
    return "\n".join(lines)
