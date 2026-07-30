"""How a CUAD annotation becomes (or fails to become) a gold clause label.

The rule these guard is "the highlight has to cover the clause it labels".
CUAD answers 41 questions about a contract rather than classifying clauses, so
its highlight for one answer routinely sits inside a clause about something
else - and the old rule, which took whichever clause a highlight *started* in,
turned that into a label. A clause headed "6.02. Termination" whose only
annotation was ``Change Of Control`` (11% of the clause) came out as gold
``other``, and a classifier answering ``termination`` was scored wrong for it.
"""

from __future__ import annotations

import pytest

from app.schemas import ClauseType, RiskLevel
from scripts.build_cuad_fixtures import (
    MIN_LABEL_COVERAGE,
    _pick_label,
    covered_characters,
)

# --- coverage arithmetic -----------------------------------------------------


def test_coverage_counts_the_part_inside_the_clause() -> None:
    assert covered_characters([(50, 150)], 100, 200) == 50


def test_coverage_counts_overlapping_highlights_once() -> None:
    """Summing raw produced over-100% coverage on real contracts, which makes
    the ratio the threshold reads meaningless."""
    assert covered_characters([(100, 160), (140, 180)], 100, 200) == 80


def test_coverage_of_a_highlight_outside_the_clause_is_zero() -> None:
    assert covered_characters([(0, 50), (300, 400)], 100, 200) == 0


# --- label selection ---------------------------------------------------------


def test_the_category_covering_most_of_the_clause_wins() -> None:
    label = _pick_label({"Governing Law": 800, "Cap On Liability": 100}, clause_length=1000)

    assert label is not None
    clause_type, _risk, coverage = label
    assert clause_type is ClauseType.GOVERNING_LAW
    assert coverage == pytest.approx(0.8)


def test_an_incidental_highlight_leaves_the_clause_unlabelled() -> None:
    """The measured case: ``Change Of Control`` covering 11% of a clause headed
    "6.02. Termination". Unlabelled is the honest answer - CUAD did not say what
    this clause is, and ``run_eval`` already skips unlabelled clauses for
    classification while still counting them for segmentation."""
    assert _pick_label({"Change Of Control": 137}, clause_length=1244) is None


def test_the_threshold_boundary_is_inclusive() -> None:
    length = 1000
    at_threshold = int(MIN_LABEL_COVERAGE * length)

    assert _pick_label({"Non-Compete": at_threshold}, clause_length=length) is not None
    assert _pick_label({"Non-Compete": at_threshold - 1}, clause_length=length) is None


def test_risk_is_the_worst_among_the_winning_types_categories() -> None:
    """A clause that caps liability and then carves an uncapped exception out of
    the cap is an uncapped-liability clause to the reviewer."""
    label = _pick_label({"Cap On Liability": 600, "Uncapped Liability": 200}, clause_length=1000)

    assert label is not None
    clause_type, risk, _coverage = label
    assert clause_type is ClauseType.LIMITATION_OF_LIABILITY
    assert risk is RiskLevel.HIGH


def test_a_category_of_another_type_does_not_set_the_risk() -> None:
    """``Governing Law`` is LOW risk and ``Non-Compete`` HIGH; the winner's own
    type decides, not whatever else happened to overlap."""
    label = _pick_label({"Governing Law": 900, "Non-Compete": 100}, clause_length=1000)

    assert label is not None
    assert label[1] is RiskLevel.LOW


def test_nothing_annotated_means_no_label() -> None:
    assert _pick_label({}, clause_length=1000) is None


def test_coverage_is_capped_at_one() -> None:
    """A highlight can run past a clause boundary; the ratio must stay readable."""
    label = _pick_label({"Insurance": 5000}, clause_length=1000)

    assert label is not None
    assert label[2] == 1.0
