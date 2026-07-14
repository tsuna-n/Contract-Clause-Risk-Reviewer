"""Evaluation metrics: span IoU / segmentation F1, accuracy, citation validity."""

from __future__ import annotations

from app.schemas.clause import Span


def span_iou(a: Span, b: Span) -> float:
    """Intersection-over-union of two character spans."""
    inter = max(0, min(a.end, b.end) - max(a.start, b.start))
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def segmentation_f1(
    predicted: list[Span],
    gold: list[Span],
    iou_threshold: float = 0.5,
) -> float:
    """Span-IoU F1 for clause segmentation.

    TODO: greedily match predicted<->gold spans above ``iou_threshold`` and
    compute precision/recall/F1.
    """
    raise NotImplementedError


def accuracy(predicted: list[str], gold: list[str]) -> float:
    """Simple label accuracy over aligned prediction/gold lists."""
    if not gold:
        return 0.0
    correct = sum(p == g for p, g in zip(predicted, gold, strict=True))
    return correct / len(gold)


def citation_validity_rate(valid: int, total: int) -> float:
    """Fraction of citations that reference a real playbook position."""
    return valid / total if total else 0.0
