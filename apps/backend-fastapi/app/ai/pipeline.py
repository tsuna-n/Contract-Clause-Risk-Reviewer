"""Pipeline orchestrator: run every agent over a document, isolate failures."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from app.ai.agents import (
    Classifier,
    Judge,
    Matcher,
    MetadataExtractor,
    RiskScorer,
    RiskScorerInput,
    Segmenter,
)
from app.ai.guardrails import disclaimer_text
from app.config import get_settings
from app.errors import PayloadTooLargeError
from app.logger import get_logger
from app.parsers import ParsedDocument
from app.schemas import (
    Clause,
    ClauseReview,
    ContractMetadata,
    ContractReviewReport,
    RiskLevel,
    RiskSummary,
)

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
        metadata_extractor: MetadataExtractor | None = None,
    ) -> None:
        self.segmenter = segmenter
        self.classifier = classifier
        self.matcher = matcher
        self.risk_scorer = risk_scorer
        self.judge = judge
        # Optional: ``None`` turns the header panel off and saves one LLM call
        # per review (``ENABLE_METADATA_EXTRACTION=false``). Reports then carry
        # empty metadata, which is exactly what the UI renders as "not stated".
        self.metadata_extractor = metadata_extractor

    def review(
        self,
        document: ParsedDocument,
        *,
        contract_id: str,
        session_id: str,
        max_clauses: int | None = None,
    ) -> ContractReviewReport:
        """Review a parsed contract and return a report.

        ``max_clauses`` refuses a document instead of starting on it. Checked
        here because segmentation is the only step that knows how many clauses
        there are, and it is the last moment before the expensive part begins:
        every clause past this point is roughly four LLM calls and twenty
        seconds. ``None`` means no ceiling, which is what the evaluation
        harness runs with - it is scoring the pipeline, not serving a request.
        """
        clauses = self.segmenter.run(document)
        if max_clauses is not None and len(clauses) > max_clauses:
            raise PayloadTooLargeError(
                f"document has {len(clauses)} clauses, above the {max_clauses}-clause "
                "limit for one review"
            )
        self._prewarm_embeddings(clauses)
        reviews, metadata = self._run_clauses_and_metadata(clauses, document)
        summary, overall = aggregate(reviews)

        return ContractReviewReport(
            report_id=uuid.uuid4().hex,
            contract_id=contract_id,
            session_id=session_id,
            overall_risk=overall,
            summary=summary,
            reviews=reviews,
            metadata=metadata,
            disclaimer=disclaimer_text(),
        )

    def _run_clauses_and_metadata(
        self, clauses: list[Clause], document: ParsedDocument
    ) -> tuple[list[ClauseReview], ContractMetadata]:
        """Review every clause and extract document metadata concurrently.

        Both are dominated by network latency, not CPU, and neither depends on
        the other, so running them on worker threads overlaps their wall clock
        instead of summing it - metadata extraction used to run only after
        every clause had finished, for no reason but the order they were
        written in. ``executor.map`` preserves input order in its results even
        though the work completes out of order, so ``reviews`` still lines up
        with ``clauses``.
        """
        if not clauses:
            return [], self._extract_metadata(document)

        concurrency = max(1, get_settings().review_concurrency)
        workers = min(concurrency, len(clauses)) + (1 if self.metadata_extractor else 0)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            metadata_future = executor.submit(self._extract_metadata, document)
            reviews = list(executor.map(self._review_clause, clauses))
            metadata = metadata_future.result()
        return reviews, metadata

    def _prewarm_embeddings(self, clauses: list[Clause]) -> None:
        """Embed the whole document in one request, or carry on without it.

        Turns N embedding requests per review into one (see
        :meth:`~app.ai.retrieval.Retriever.prewarm`). Isolated like every other
        step here: if the pre-warm fails, each clause embeds on its own the way
        it always did, and the retry inside the embedder gets a second chance
        at whatever went wrong — so a failure here costs quota, never a report.
        """
        try:
            self.matcher.prewarm(clauses)
        except Exception:
            logger.warning("embedding pre-warm failed; clauses will embed one by one")

    def _extract_metadata(self, document: ParsedDocument) -> ContractMetadata:
        """Read the contract's header facts, or return empty if that fails.

        Isolated like a clause failure is: the parties and dates are context
        for the risk assessment, never the reason it was run, so losing them
        must not cost the reviewer a report they waited minutes for.
        """
        if self.metadata_extractor is None:
            return ContractMetadata()
        try:
            return self.metadata_extractor.run(document)
        except Exception:
            logger.warning("contract metadata extraction failed", exc_info=True)
            return ContractMetadata()

    def _review_clause(self, clause: Clause) -> ClauseReview:
        """Run one clause through classify -> match -> score -> judge.

        A single retry is allowed when the judge flags the first pass as
        ungrounded, and it carries the judge's reason back to the scorer: the
        retry used to re-send the identical prompt, which mostly bought the
        identical answer for twice the tokens. Any exception isolates the
        failure to this clause instead of failing the whole report.
        """
        try:
            clause.clause_type = self.classifier.run(clause)
            hits = self.matcher.run(clause)
            review = self.risk_scorer.run(RiskScorerInput(clause=clause, hits=hits))
            verdict = self.judge.run(review)
            if not verdict.grounded and verdict.should_retry:
                review = self.risk_scorer.run(
                    RiskScorerInput(clause=clause, hits=hits, feedback=verdict.reason)
                )
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
