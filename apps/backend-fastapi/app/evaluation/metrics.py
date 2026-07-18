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

    Greedily matches each predicted span to its best unmatched gold span
    above ``iou_threshold``, then computes precision/recall/F1.
    """
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0

    remaining = list(gold)
    matches = 0
    for pred in predicted:
        best_idx, best_iou = None, 0.0
        for idx, candidate in enumerate(remaining):
            iou = span_iou(pred, candidate)
            if iou >= iou_threshold and iou > best_iou:
                best_idx, best_iou = idx, iou
        if best_idx is not None:
            matches += 1
            del remaining[best_idx]

    precision = matches / len(predicted)
    recall = matches / len(gold)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def accuracy(predicted: list[str], gold: list[str]) -> float:
    """Simple label accuracy over aligned prediction/gold lists."""
    if not gold:
        return 0.0
    correct = sum(p == g for p, g in zip(predicted, gold, strict=True))
    return correct / len(gold)


def citation_validity_rate(valid: int, total: int) -> float:
    """Fraction of citations that reference a real playbook position."""
    return valid / total if total else 0.0
