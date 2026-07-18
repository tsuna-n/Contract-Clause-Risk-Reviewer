"""Unit tests for report-level risk aggregation."""

from app.agents.orchestrator import aggregate
from app.schemas.clause import Clause, ClauseReview, Span
from app.schemas.taxonomy import RiskLevel


def _review(risk: RiskLevel) -> ClauseReview:
    clause = Clause(id="c", text="t", span=Span(start=0, end=1))
    return ClauseReview(clause=clause, risk_level=risk)


def test_aggregate_worst_case_wins() -> None:
    reviews = [_review(RiskLevel.LOW), _review(RiskLevel.HIGH), _review(RiskLevel.MEDIUM)]
    summary, overall = aggregate(reviews)
    assert overall == RiskLevel.HIGH
    assert summary.low == 1
    assert summary.medium == 1
    assert summary.high == 1
    assert summary.unknown == 0


def test_aggregate_all_unknown() -> None:
    summary, overall = aggregate([_review(RiskLevel.UNKNOWN)])
    assert overall == RiskLevel.UNKNOWN
    assert summary.unknown == 1


def test_aggregate_empty_reviews() -> None:
    summary, overall = aggregate([])
    assert overall == RiskLevel.UNKNOWN
    assert summary.high == summary.medium == summary.low == summary.unknown == 0
