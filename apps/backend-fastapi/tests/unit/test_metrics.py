"""Unit tests for evaluation metrics."""

from app.evaluation.metrics import accuracy, citation_validity_rate, span_iou
from app.evaluation.report import confusion_matrix
from app.schemas.clause import Span


def test_span_iou_full_overlap() -> None:
    assert span_iou(Span(start=0, end=10), Span(start=0, end=10)) == 1.0


def test_span_iou_no_overlap() -> None:
    assert span_iou(Span(start=0, end=5), Span(start=5, end=10)) == 0.0


def test_span_iou_partial() -> None:
    # intersection=5, union=15 -> 1/3
    assert span_iou(Span(start=0, end=10), Span(start=5, end=15)) == 5 / 15


def test_accuracy() -> None:
    assert accuracy(["a", "b", "c"], ["a", "x", "c"]) == 2 / 3


def test_citation_validity_rate() -> None:
    assert citation_validity_rate(3, 4) == 0.75
    assert citation_validity_rate(0, 0) == 0.0


def test_confusion_matrix() -> None:
    matrix = confusion_matrix(["a", "b", "a"], ["a", "a", "a"])
    assert matrix["a"]["a"] == 2
    assert matrix["a"]["b"] == 1
