"""Clauses review concurrently instead of one at a time.

``Orchestrator._review_clause`` used to run in a plain sequential list
comprehension, so a review's wall clock was every clause's calls summed.
``review_concurrency`` bounds how many run on worker threads at once instead.
"""

from __future__ import annotations

import threading
import time

from app.ai.agents import Verdict
from app.ai.pipeline import Orchestrator
from app.config import get_settings
from app.parsers import ParsedDocument, TextSpan
from app.schemas import Clause, ClauseReview, ClauseType, RiskLevel, Span


class _FixedAgent:
    def __init__(self, answer) -> None:
        self._answer = answer

    def run(self, _payload):
        return self._answer


class _SlowTrackingScorer:
    """Sleeps on every call and records the most calls seen in flight at once."""

    def __init__(self, delay: float) -> None:
        self._delay = delay
        self._lock = threading.Lock()
        self._in_flight = 0
        self.max_in_flight = 0

    def run(self, payload) -> ClauseReview:
        with self._lock:
            self._in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self._in_flight)
        time.sleep(self._delay)
        with self._lock:
            self._in_flight -= 1
        return ClauseReview(clause=payload.clause, risk_level=RiskLevel.LOW, rationale="ok")


def _clauses(n: int) -> list[Clause]:
    return [
        Clause(id=f"clause-{i}", text=f"clause {i} text", span=Span(start=0, end=1))
        for i in range(n)
    ]


def _document() -> ParsedDocument:
    text = "doc"
    return ParsedDocument(
        text=text, spans=[TextSpan(start=0, end=len(text), page=1)], page_map={1: (0, len(text))}
    )


def test_clauses_review_concurrently_up_to_the_configured_limit(monkeypatch) -> None:
    monkeypatch.setenv("REVIEW_CONCURRENCY", "4")
    get_settings.cache_clear()
    try:
        clauses = _clauses(8)
        scorer = _SlowTrackingScorer(delay=0.05)
        orchestrator = Orchestrator(
            segmenter=_FixedAgent(clauses),
            classifier=_FixedAgent(ClauseType.OTHER),
            matcher=_FixedAgent([]),
            risk_scorer=scorer,
            judge=_FixedAgent(Verdict(grounded=True)),
        )

        start = time.monotonic()
        report = orchestrator.review(_document(), contract_id="c1", session_id="user-1")
        elapsed = time.monotonic() - start

        # Results still line up with the clauses they came from even though
        # the work that produced them finished out of order.
        assert [r.clause.id for r in report.reviews] == [c.id for c in clauses]
        # More than one call was in flight at once - this was never true of
        # the old sequential loop - and never more than the configured limit.
        assert 1 < scorer.max_in_flight <= 4
        # 8 clauses at 0.05s fully serial would take ~0.4s; four at a time
        # takes two batches, ~0.1s. Generous slack for a loaded test runner.
        assert elapsed < 0.3
    finally:
        get_settings.cache_clear()


def test_metadata_extraction_overlaps_clause_review_instead_of_waiting() -> None:
    """Metadata extraction used to run only after every clause had finished.

    It reads the whole document, not any one clause, so there is no reason
    for it to wait - overlapping it with the clause loop should make a review
    take roughly as long as the slower of the two, not their sum.
    """

    class _SlowMetadataExtractor:
        def __init__(self, delay: float) -> None:
            self._delay = delay

        def run(self, _document):
            time.sleep(self._delay)
            from app.schemas import ContractMetadata

            return ContractMetadata()

    clauses = _clauses(1)
    scorer = _SlowTrackingScorer(delay=0.1)
    orchestrator = Orchestrator(
        segmenter=_FixedAgent(clauses),
        classifier=_FixedAgent(ClauseType.OTHER),
        matcher=_FixedAgent([]),
        risk_scorer=scorer,
        judge=_FixedAgent(Verdict(grounded=True)),
        metadata_extractor=_SlowMetadataExtractor(delay=0.1),
    )

    start = time.monotonic()
    orchestrator.review(_document(), contract_id="c1", session_id="user-1")
    elapsed = time.monotonic() - start

    # Sequential would be >= 0.2s (0.1 for the clause + 0.1 for metadata);
    # overlapped, it should land close to the slower one alone.
    assert elapsed < 0.18
