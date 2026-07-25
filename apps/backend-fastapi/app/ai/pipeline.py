"""Pipeline orchestrator: run every agent over a document, isolate failures."""

from __future__ import annotations

import uuid

from app.ai.agents import Classifier, Judge, Matcher, RiskScorer, RiskScorerInput, Segmenter
from app.ai.guardrails import disclaimer_text
from app.logger import get_logger
from app.parsers import ParsedDocument
from app.schemas import Clause, ClauseReview, ContractReviewReport, RiskLevel, RiskSummary

logger = get_logger(__name__)


def aggregate(reviews: list[ClauseReview]) -> tuple[RiskSummary, RiskLevel]:
    """Aggregate per-clause reviews into a report-level summary + overall risk.

    Overall risk is "worst case wins": a report is only as safe as its
    riskiest clause.
    """
    summary = RiskSummary()
    for review in reviews:
        if review.risk_level == RiskLevel.HIGH:
            summary.high += 1
        elif review.risk_level == RiskLevel.MEDIUM:
            summary.medium += 1
        elif review.risk_level == RiskLevel.LOW:
            summary.low += 1
        else:
            summary.unknown += 1

    if summary.high:
        overall = RiskLevel.HIGH
    elif summary.medium:
        overall = RiskLevel.MEDIUM
    elif summary.low:
        overall = RiskLevel.LOW
    else:
        overall = RiskLevel.UNKNOWN
    return summary, overall


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
        """Review a parsed contract and return a report."""
        clauses = self.segmenter.run(document)
        reviews = [self._review_clause(clause) for clause in clauses]
        summary, overall = aggregate(reviews)

        return ContractReviewReport(
            report_id=uuid.uuid4().hex,
            contract_id=contract_id,
            session_id=session_id,
            overall_risk=overall,
            summary=summary,
            reviews=reviews,
            disclaimer=disclaimer_text(),
        )

    def _review_clause(self, clause: Clause) -> ClauseReview:
        """Run one clause through classify -> match -> score -> judge.

        A single retry is allowed when the judge flags the first pass as
        ungrounded. Any exception isolates the failure to this clause instead
        of failing the whole report.
        """
        try:
            clause.clause_type = self.classifier.run(clause)
            hits = self.matcher.run(clause)
            review = self.risk_scorer.run(RiskScorerInput(clause=clause, hits=hits))
            verdict = self.judge.run(review)
            if not verdict.grounded and verdict.should_retry:
                review = self.risk_scorer.run(RiskScorerInput(clause=clause, hits=hits))
                verdict = self.judge.run(review)
            review.verified = verdict.grounded
            return review
        except Exception:
            logger.warning("clause %s review failed", clause.id, exc_info=True)
            return ClauseReview(
                clause=clause,
                risk_level=RiskLevel.UNKNOWN,
                rationale="Automated review failed for this clause; manual review required.",
            )
