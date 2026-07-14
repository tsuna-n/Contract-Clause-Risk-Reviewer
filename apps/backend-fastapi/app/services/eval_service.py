"""Evaluation service: run the gold set through the pipeline."""

from __future__ import annotations

from app.schemas.eval import EvalMetrics, EvalRequest


class EvalService:
    """Runs the evaluation harness and returns aggregate metrics."""

    def run(self, request: EvalRequest) -> EvalMetrics:
        """Evaluate the pipeline against a gold set.

        TODO: delegate to ``evaluation.runner`` and return EvalMetrics.
        """
        raise NotImplementedError
