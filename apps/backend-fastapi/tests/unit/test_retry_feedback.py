"""The retry the orchestrator allows when the judge rejects a review.

It used to re-send the identical prompt, which mostly bought the identical
answer for twice the tokens. Now it carries the judge's reason back to the
scorer, so the second attempt is told what was wrong with the first.
"""

from __future__ import annotations

from app.ai.agents import RiskScorerInput, Verdict, render_prompt
from app.ai.pipeline import Orchestrator
from app.parsers import ParsedDocument, TextSpan
from app.schemas import Clause, ClauseReview, ClauseType, RiskLevel, Span


class _Recorder:
    """A risk scorer that records what it was asked and answers the same way."""

    def __init__(self) -> None:
        self.inputs: list[RiskScorerInput] = []

    def run(self, payload: RiskScorerInput) -> ClauseReview:
        self.inputs.append(payload)
        return ClauseReview(clause=payload.clause, risk_level=RiskLevel.HIGH, rationale="uncapped")


class _RejectingJudge:
    """Rejects the first review, accepts the second."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.calls = 0

    def run(self, _review) -> Verdict:
        self.calls += 1
        if self.calls == 1:
            return Verdict(grounded=False, reason=self.reason, should_retry=True)
        return Verdict(grounded=True, reason="deterministic checks passed")


class _FixedAgent:
    def __init__(self, answer) -> None:
        self._answer = answer

    def run(self, _payload):
        return self._answer


def _document() -> ParsedDocument:
    text = "1. Liability\nUnlimited liability for all damages."
    return ParsedDocument(
        text=text, spans=[TextSpan(start=0, end=len(text), page=1)], page_map={1: (0, len(text))}
    )


def test_the_retry_tells_the_scorer_why_the_first_answer_was_rejected() -> None:
    scorer = _Recorder()
    judge = _RejectingJudge("excerpt for citation c1 is not a verbatim quote")
    orchestrator = Orchestrator(
        segmenter=_FixedAgent(
            [Clause(id="clause-1", text="Unlimited liability.", span=Span(start=0, end=20))]
        ),
        classifier=_FixedAgent(ClauseType.LIMITATION_OF_LIABILITY),
        matcher=_FixedAgent([]),
        risk_scorer=scorer,
        judge=judge,
    )

    report = orchestrator.review(_document(), contract_id="c1", session_id="user-1")

    assert len(scorer.inputs) == 2
    assert scorer.inputs[0].feedback is None
    assert scorer.inputs[1].feedback == "excerpt for citation c1 is not a verbatim quote"
    # The second verdict is the one that counts.
    assert report.reviews[0].verified is True


def test_a_first_pass_that_is_accepted_never_asks_twice() -> None:
    scorer = _Recorder()
    orchestrator = Orchestrator(
        segmenter=_FixedAgent(
            [Clause(id="clause-1", text="Unlimited liability.", span=Span(start=0, end=20))]
        ),
        classifier=_FixedAgent(ClauseType.LIMITATION_OF_LIABILITY),
        matcher=_FixedAgent([]),
        risk_scorer=scorer,
        judge=_FixedAgent(Verdict(grounded=True)),
    )

    orchestrator.review(_document(), contract_id="c1", session_id="user-1")

    assert len(scorer.inputs) == 1


def test_the_scorer_prompt_carries_the_feedback_and_omits_it_otherwise() -> None:
    """The feedback has to reach the model, not just the dataclass."""
    rendered = render_prompt(
        "risk_scorer.v1.jinja",
        clause_type="limitation_of_liability",
        clause_text="Unlimited liability.",
        hits=[],
        feedback="excerpt for citation c1 is not a verbatim quote",
    )
    assert "previous answer for this clause was rejected" in rendered
    assert "not a verbatim quote" in rendered

    clean = render_prompt(
        "risk_scorer.v1.jinja",
        clause_type="limitation_of_liability",
        clause_text="Unlimited liability.",
        hits=[],
        feedback=None,
    )
    assert "previous answer" not in clean
