"""``run_eval`` against the gold-set format the CUAD fixtures are written in.

The point of interest is the clause with a span but no ``clause_type``. The
fixtures are built from CUAD, whose 41 categories don't cover the whole
taxonomy, so a segment CUAD never annotated has a real boundary and no expert
label. It has to count towards segmentation and be left out of
classification/risk, or the pipeline would be scored against a label nobody
ever assigned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.agents import Segmenter
from app.parsers import ParsedDocument, TextSpan, normalize
from app.schemas import (
    Clause,
    ClauseReview,
    ClauseType,
    ContractReviewReport,
    RiskLevel,
    Span,
)
from app.services.evaluation import run_eval

CONTRACT_TEXT = (
    "1. Termination. Either party may terminate on thirty (30) days' notice.\n\n"
    "2. Notices. Notices shall be sent to the addresses on the cover page.\n"
)


class StubOrchestrator:
    """Returns one review per gold span, with the labels the test dictates."""

    def __init__(self, labels: list[tuple[ClauseType, RiskLevel]], spans: list[Span]) -> None:
        self._labels = labels
        self._spans = spans

    def review(
        self, document: ParsedDocument, *, contract_id: str, session_id: str
    ) -> ContractReviewReport:
        reviews = [
            ClauseReview(
                clause=Clause(
                    id=f"clause-{i + 1}",
                    text=document.text[span.start : span.end],
                    span=span,
                    clause_type=clause_type,
                ),
                risk_level=risk,
            )
            for i, (span, (clause_type, risk)) in enumerate(
                zip(self._spans, self._labels, strict=True)
            )
        ]
        return ContractReviewReport(
            report_id="r1", contract_id=contract_id, session_id=session_id, reviews=reviews
        )


@pytest.fixture()
def gold_set(tmp_path: Path) -> tuple[Path, list[Span]]:
    """A one-contract gold set: clause 1 labelled, clause 2 boundary-only."""
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "sample.txt").write_text(CONTRACT_TEXT)

    # Gold spans come from the real segmenter, exactly as
    # scripts/build_cuad_fixtures.py builds them — hand-counted offsets would
    # only be right until someone touched the normalizer.
    text = normalize(CONTRACT_TEXT)
    document = ParsedDocument(
        text=text, spans=[TextSpan(start=0, end=len(text), page=1)], page_map={1: (0, len(text))}
    )
    spans = [clause.span for clause in Segmenter(None).run(document)]
    assert len(spans) == 2
    record = {
        "contract_id": "sample",
        "clauses": [
            {
                "span": {"start": spans[0].start, "end": spans[0].end},
                "clause_type": "termination",
                "risk_level": "medium",
            },
            # No clause_type: CUAD has no category for a notices clause.
            {"span": {"start": spans[1].start, "end": spans[1].end}},
        ],
    }

    gold = tmp_path / "gold" / "annotations.jsonl"
    gold.parent.mkdir()
    gold.write_text(json.dumps(record) + "\n")
    return gold, spans


def test_unlabelled_clause_counts_for_segmentation_only(gold_set) -> None:
    gold, spans = gold_set
    # The pipeline gets clause 2 "wrong" — but there is no gold label to be
    # wrong about, so accuracy must stay at 1.0 on the strength of clause 1.
    orchestrator = StubOrchestrator(
        [(ClauseType.TERMINATION, RiskLevel.MEDIUM), (ClauseType.WARRANTY, RiskLevel.HIGH)],
        spans,
    )

    metrics = run_eval(gold, orchestrator=orchestrator, known_position_ids=set())

    assert metrics.segmentation_f1 == 1.0  # both boundaries were predicted
    assert metrics.classification_accuracy == 1.0
    assert metrics.risk_accuracy == 1.0
    assert [(row.clause_type, row.support) for row in metrics.per_type] == [
        (ClauseType.TERMINATION, 1)
    ]


def test_labelled_clause_is_still_scored(gold_set) -> None:
    gold, spans = gold_set
    orchestrator = StubOrchestrator(
        [(ClauseType.WARRANTY, RiskLevel.LOW), (ClauseType.OTHER, RiskLevel.LOW)],
        spans,
    )

    metrics = run_eval(gold, orchestrator=orchestrator, known_position_ids=set())

    assert metrics.classification_accuracy == 0.0
    assert metrics.risk_accuracy == 0.0


def test_contract_ids_selects_which_contracts_run(gold_set) -> None:
    """A full run is ~1,300 LLM calls; naming one contract is how you afford a check."""
    gold, spans = gold_set
    orchestrator = StubOrchestrator(
        [(ClauseType.TERMINATION, RiskLevel.MEDIUM), (ClauseType.WARRANTY, RiskLevel.HIGH)],
        spans,
    )

    metrics = run_eval(
        gold,
        orchestrator=orchestrator,
        known_position_ids=set(),
        contract_ids={"some-other-contract"},
    )

    # Nothing matched, so nothing was run - and nothing was billed.
    assert metrics.per_type == []
    assert metrics.segmentation_f1 == 1.0  # vacuously: no predictions, no gold


def test_missing_contract_fixture_is_skipped_not_fatal(tmp_path: Path) -> None:
    gold = tmp_path / "gold" / "annotations.jsonl"
    gold.parent.mkdir(parents=True)
    gold.write_text(json.dumps({"contract_id": "nope", "clauses": []}) + "\n")

    metrics = run_eval(gold, orchestrator=StubOrchestrator([], []), known_position_ids=set())

    assert metrics.classification_accuracy == 0.0
