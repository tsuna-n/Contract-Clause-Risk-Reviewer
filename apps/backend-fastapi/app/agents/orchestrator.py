"""Pipeline orchestrator: batching + partial-failure handling."""

from __future__ import annotations

from app.agents.classifier import Classifier
from app.agents.judge import Judge
from app.agents.matcher import Matcher
from app.agents.risk_scorer import RiskScorer
from app.agents.segmenter import Segmenter
from app.parsers.models import ParsedDocument
from app.schemas.report import ContractReviewReport


class Orchestrator:
    """Runs the full segment -> classify -> match -> score -> judge pipeline."""

    def __init__(
        self,
        segmenter: Segmenter,
        classifier: Classifier,
        matcher: Matcher,
        risk_scorer: RiskScorer,
        judge: Judge,
    ) -> None:
        self.segmenter = segmenter
        self.classifier = classifier
        self.matcher = matcher
        self.risk_scorer = risk_scorer
        self.judge = judge

    def review(
        self,
        document: ParsedDocument,
        *,
        contract_id: str,
        session_id: str,
    ) -> ContractReviewReport:
        """Review a parsed contract and return a report.

        TODO: segment the document, then for each clause run classify -> match
        -> score -> judge (batched, with per-clause failures isolated so one bad
        clause doesn't fail the whole report), aggregate the risk summary, and
        attach the disclaimer.
        """
        raise NotImplementedError
