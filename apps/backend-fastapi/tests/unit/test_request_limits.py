"""Unit tests for the three limits that keep one request from taking the server.

Each of these was an open hole until 2026-07-30, and each fails in a way that
looks like something else: an unbounded upload looks like a memory leak, an
unbounded clause count looks like a hung request, a client-supplied gold-set
path looks like a parse error while it reads whatever it was pointed at.
"""

from __future__ import annotations

import inspect

import pytest

from app.ai.agents import Verdict
from app.ai.pipeline import Orchestrator
from app.errors import InvalidInputError, PayloadTooLargeError
from app.parsers import ParsedDocument, TextSpan
from app.routes import auth, contracts, evaluate, health, playbook
from app.schemas import Clause, ClauseReview, ClauseType, RiskLevel, Span
from app.services.evaluation import resolve_gold_set_path

# --- clause ceiling ----------------------------------------------------------


class _StubSegmenter:
    """Returns ``count`` clauses without looking at the document."""

    def __init__(self, count: int) -> None:
        self.count = count

    def run(self, _document) -> list[Clause]:
        return [
            Clause(id=f"clause-{i}", text="Unlimited liability.", span=Span(start=0, end=20))
            for i in range(self.count)
        ]


class _CountingClassifier:
    """Stands in for the first agent a clause reaches, and counts arrivals.

    Counted rather than made to raise: the orchestrator isolates a failing
    clause on purpose, so an exception here would be swallowed and prove
    nothing about whether the work started.
    """

    def __init__(self) -> None:
        self.calls = 0

    def run(self, _clause) -> ClauseType:
        self.calls += 1
        return ClauseType.OTHER


class _FixedAgent:
    """Returns the same answer for any input."""

    def __init__(self, answer) -> None:
        self._answer = answer

    def run(self, _payload):
        return self._answer


class _StubRiskScorer:
    """Echoes the clause back as an unscored review, without calling an LLM."""

    def run(self, payload) -> ClauseReview:
        return ClauseReview(clause=payload.clause, risk_level=RiskLevel.UNKNOWN)


def _orchestrator(clause_count: int) -> tuple[Orchestrator, _CountingClassifier]:
    classifier = _CountingClassifier()
    orchestrator = Orchestrator(
        segmenter=_StubSegmenter(clause_count),
        classifier=classifier,
        matcher=_FixedAgent([]),
        risk_scorer=_StubRiskScorer(),
        judge=_FixedAgent(Verdict(grounded=True)),
    )
    return orchestrator, classifier


def _document() -> ParsedDocument:
    text = "1. Liability\nUnlimited."
    return ParsedDocument(
        text=text, spans=[TextSpan(start=0, end=len(text), page=1)], page_map={1: (0, len(text))}
    )


def test_a_document_over_the_clause_ceiling_is_refused_before_any_llm_call() -> None:
    """The point of the check is where it sits: after segmentation (the only
    step that can count clauses) and before the ~4 LLM calls per clause."""
    orchestrator, classifier = _orchestrator(301)

    with pytest.raises(PayloadTooLargeError, match="301 clauses"):
        orchestrator.review(_document(), contract_id="c1", session_id="user-1", max_clauses=300)

    assert classifier.calls == 0


def test_a_document_at_the_ceiling_is_allowed() -> None:
    """Off-by-one here would reject the document that exactly fits."""
    orchestrator, classifier = _orchestrator(300)

    report = orchestrator.review(
        _document(), contract_id="c1", session_id="user-1", max_clauses=300
    )

    assert len(report.reviews) == 300
    assert classifier.calls == 300


def test_the_eval_harness_runs_without_a_ceiling() -> None:
    """``max_clauses=None`` is the default for a reason: the harness is scoring
    the pipeline, not serving a request, and a 400-clause gold contract is a
    measurement rather than an abuse."""
    orchestrator, classifier = _orchestrator(400)

    report = orchestrator.review(_document(), contract_id="c1", session_id="eval")

    assert len(report.reviews) == 400
    assert classifier.calls == 400


# --- gold-set path -----------------------------------------------------------


def test_the_default_gold_set_path_is_accepted() -> None:
    assert resolve_gold_set_path("data/gold/annotations.jsonl").endswith(
        "data/gold/annotations.jsonl"
    )


@pytest.mark.parametrize(
    "path",
    [
        "data/gold/../../.env",  # traversal that resolves outside
        "/etc/passwd",  # absolute, elsewhere
        ".env",  # relative, elsewhere
        "data/playbook/positions.yaml",  # inside the repo, still not a gold set
    ],
)
def test_a_gold_set_path_outside_the_gold_directory_is_refused(path) -> None:
    """``gold_set_path`` arrives in the request body. Rejected on what it
    resolves to, not on how it is spelled, or ``data/gold/../../.env`` passes."""
    with pytest.raises(InvalidInputError, match="must be inside"):
        resolve_gold_set_path(path)


# --- event loop --------------------------------------------------------------

#: Endpoints allowed to be ``async def``, and why. Everything else in these
#: modules does blocking work - a DB query, Redis, or the review pipeline - and
#: must be a plain ``def`` so FastAPI runs it in a worker thread instead of on
#: the event loop, where it would stall every other request including
#: ``/health``.
_ASYNC_ALLOWED = {
    "review_contract",  # awaits the upload, then hands the pipeline to a thread
    "google_login",  # awaits authlib
    "google_callback",  # awaits authlib
}


@pytest.mark.parametrize("module", [contracts, playbook, evaluate, health, auth])
def test_blocking_endpoints_do_not_run_on_the_event_loop(module) -> None:
    offenders = [
        name
        for name, func in vars(module).items()
        if inspect.iscoroutinefunction(func)
        # Defined here, not imported: ``run_in_threadpool`` is itself a
        # coroutine function and lives in this namespace by design.
        and getattr(func, "__module__", None) == module.__name__
        and name not in _ASYNC_ALLOWED
    ]
    assert offenders == [], (
        f"{module.__name__}: {offenders} are async but do blocking work; "
        "either make them `def` or move the blocking part into run_in_threadpool"
    )


def test_the_review_endpoint_hands_the_pipeline_to_a_worker_thread() -> None:
    """It is the one endpoint that has to stay async, so the delegation is the
    only thing keeping a six-minute review off the event loop."""
    source = inspect.getsource(contracts.review_contract)
    assert "run_in_threadpool" in source
