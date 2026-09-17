"""The judge's deterministic checks, and which playbook it checks against.

The LLM half is switched off (``enable_judge=False``) so these exercise the
guardrails alone: citation validity, excerpt grounding, and no invented
fallback. What the LLM would add is a softer "the rationale doesn't overreach"
opinion, which has nothing to say about the cases below.
"""

from __future__ import annotations

import pytest

from app.ai.agents import Judge
from app.config import get_settings
from app.schemas import (
    Citation,
    Clause,
    ClauseReview,
    ClauseType,
    PlaybookPosition,
    RiskLevel,
    Span,
)


@pytest.fixture(autouse=True)
def deterministic_only(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_judge", False)
    return settings


def position(position_id: str) -> PlaybookPosition:
    return PlaybookPosition(
        id=position_id,
        clause_type=ClauseType.TERMINATION,
        title="Termination for convenience",
        preferred_language="Either party may terminate on thirty (30) days' notice.",
        fallback_language="Either party may terminate on sixty (60) days' notice.",
    )


def review(*, cites: str, excerpt: str = "terminate on thirty (30) days") -> ClauseReview:
    return ClauseReview(
        clause=Clause(id="clause-1", text="Termination.", span=Span(start=0, end=12)),
        risk_level=RiskLevel.MEDIUM,
        rationale="Shorter notice than the playbook asks for.",
        citations=[
            Citation(citation_id="c1", playbook_position_id=cites, excerpt=excerpt),
        ],
    )


def test_accepts_a_grounded_citation() -> None:
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})  # type: ignore[arg-type]

    assert judge.run(review(cites="pb-1")).grounded


def test_rejects_a_citation_to_an_unknown_position() -> None:
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})  # type: ignore[arg-type]

    verdict = judge.run(review(cites="pb-does-not-exist"))

    assert not verdict.grounded
    assert verdict.should_retry


def test_rejects_an_excerpt_that_is_not_in_the_cited_position() -> None:
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})  # type: ignore[arg-type]

    verdict = judge.run(review(cites="pb-1", excerpt="terminate immediately without notice"))

    assert not verdict.grounded


@pytest.mark.parametrize("excerpt", ["the", "on", "notice.", "may terminate"])
def test_rejects_an_excerpt_too_short_to_be_evidence(excerpt: str) -> None:
    """A bare substring check hands out ``verified`` for quoting a stopword.

    ``"the"`` appears in every playbook position ever written, so before the
    minimum length a review could be marked grounded while quoting nothing that
    supports it - the worst kind of failure here, because the badge says the
    opposite of what happened.
    """
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})  # type: ignore[arg-type]

    verdict = judge.run(review(cites="pb-1", excerpt=excerpt))

    assert not verdict.grounded
    assert "at least" in verdict.reason
    assert verdict.should_retry


def test_the_rejection_reason_names_what_to_fix() -> None:
    """The reason is fed back into the retry, so it has to be actionable."""
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})  # type: ignore[arg-type]

    verdict = judge.run(review(cites="pb-1", excerpt="terminate immediately without notice"))

    assert "verbatim quote" in verdict.reason
    assert "c1" in verdict.reason


def test_sees_positions_added_after_it_was_built() -> None:
    """The judge is a singleton; the playbook is editable at runtime.

    A position created through /playbook is retrievable straight away, so the
    matcher can hand the scorer a citation to it. If the judge held a snapshot
    from startup it would call that citation unknown and reject a review that
    is, in fact, perfectly grounded.
    """
    playbook: dict[str, PlaybookPosition] = {}
    judge = Judge(llm=None, known_positions=lambda: dict(playbook))  # type: ignore[arg-type]

    assert not judge.run(review(cites="pb-new")).grounded

    playbook["pb-new"] = position("pb-new")

    assert judge.run(review(cites="pb-new")).grounded


def test_missing_evidence_cannot_be_verified_without_the_llm() -> None:
    judge = Judge(llm=None, known_positions={"pb-1": position("pb-1")})
    assessment = review(cites="pb-1")
    assessment.citations = []
    verdict = judge.run(assessment)
    assert not verdict.grounded
    assert verdict.should_retry
    assessment.risk_level = RiskLevel.UNKNOWN
    assert not judge.run(assessment).should_retry


def test_llm_judge_receives_full_cited_sources_and_fallback(deterministic_only) -> None:
    deterministic_only.enable_judge = True
    captured = {}

    class CapturingLLM:
        def complete_structured(self, **kwargs):
            captured.update(kwargs)
            return kwargs["response_model"](grounded=True, reason="supported")

    cited = position("pb-1")
    judge = Judge(llm=CapturingLLM(), known_positions={"pb-1": cited, "unused": position("unused")})
    assessment = review(cites="pb-1")
    assessment.suggested_fallback = cited.fallback_language
    assert judge.run(assessment).grounded
    assert cited.preferred_language in captured["prompt"]
    assert cited.fallback_language in captured["prompt"]
    assert "[pb-1]" in captured["prompt"]
    assert "[unused]" not in captured["prompt"]
    assert "Claims about the contract" in captured["prompt"]
