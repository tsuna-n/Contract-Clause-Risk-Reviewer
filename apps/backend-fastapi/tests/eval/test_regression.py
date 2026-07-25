"""Eval regression gate: the pipeline must stay >= 75% accuracy."""

import pytest

from app.dependencies import get_known_positions, get_orchestrator
from app.services.evaluation import run_eval

MIN_ACCURACY = 0.75


@pytest.mark.skip(reason="pipeline not implemented yet; enable once run_eval works")
def test_regression_accuracy_gate() -> None:
    metrics = run_eval(
        "data/gold/annotations.jsonl",
        orchestrator=get_orchestrator(),
        known_position_ids=set(get_known_positions()),
    )
    assert metrics.classification_accuracy >= MIN_ACCURACY
    assert metrics.risk_accuracy >= MIN_ACCURACY
