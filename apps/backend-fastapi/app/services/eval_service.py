"""Evaluation service: run the gold set through the pipeline."""

from __future__ import annotations

from app.agents.orchestrator import Orchestrator
from app.evaluation.runner import run_eval
from app.schemas.eval import EvalMetrics, EvalRequest


class EvalService:
    """Runs the evaluation harness and returns aggregate metrics."""

    def __init__(self, orchestrator: Orchestrator, known_position_ids: set[str]) -> None:
        self.orchestrator = orchestrator
        self.known_position_ids = known_position_ids

    def run(self, request: EvalRequest) -> EvalMetrics:
        """Evaluate the pipeline against a gold set."""
        return run_eval(
            request.gold_set_path,
            orchestrator=self.orchestrator,
            known_position_ids=self.known_position_ids,
            limit=request.limit,
        )
