"""Evaluation service: run the gold set through the pipeline."""

from __future__ import annotations

from app.evaluation.runner import run_eval
from app.schemas.eval import EvalMetrics, EvalRequest


class EvalService:
    """Runs the evaluation harness and returns aggregate metrics."""

    def run(self, request: EvalRequest) -> EvalMetrics:
        """Evaluate the pipeline against a gold set."""
        return run_eval(request.gold_set_path, request.limit)
