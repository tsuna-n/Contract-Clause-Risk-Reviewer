"""Unit tests for evaluation metrics."""

from app.evaluation.metrics import accuracy, citation_validity_rate, segmentation_f1, span_iou
from app.evaluation.report import confusion_matrix, format_report
from app.schemas.clause import Span
from app.schemas.eval import EvalMetrics, PerTypeMetrics


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


def test_segmentation_f1_perfect_match() -> None:
    spans = [Span(start=0, end=10), Span(start=10, end=20)]
    assert segmentation_f1(spans, spans) == 1.0


def test_segmentation_f1_no_predictions() -> None:
    assert segmentation_f1([], [Span(start=0, end=10)]) == 0.0
    assert segmentation_f1([], []) == 1.0


def test_segmentation_f1_partial_overlap_below_threshold() -> None:
    predicted = [Span(start=0, end=10)]
    gold = [Span(start=8, end=20)]  # IoU = 2/20 = 0.1, below the 0.5 default
    assert segmentation_f1(predicted, gold) == 0.0


def test_segmentation_f1_extra_prediction_hurts_precision() -> None:
    predicted = [Span(start=0, end=10), Span(start=100, end=110)]
    gold = [Span(start=0, end=10)]
    # precision = 1/2, recall = 1/1 -> F1 = 2*0.5*1/(0.5+1) = 2/3
    assert segmentation_f1(predicted, gold) == 2 / 3


def test_format_report_includes_per_type_breakdown() -> None:
    metrics = EvalMetrics(
        segmentation_f1=1.0,
        classification_accuracy=0.5,
        risk_accuracy=0.75,
        citation_validity=1.0,
        per_type=[PerTypeMetrics(clause_type="termination", support=2, accuracy=0.5)],
    )
    report = format_report(metrics)
    assert "segmentation_f1" in report
    assert "termination" in report
