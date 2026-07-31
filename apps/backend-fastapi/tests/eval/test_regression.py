"""Eval regression gate — the pipeline's measurable properties, on real calls.

Runs the evaluation harness over one short CUAD contract against the real
provider, so it is marked ``live_llm`` and deselected from the default run
(see ``tests/live/`` for the rest of the live suite and ``pyproject.toml`` for
the marker).

**What this gate asserts, and what it deliberately doesn't.** Of the four
metrics the harness reports, only two are stable enough to fail a build on:

* ``segmentation_f1`` — no LLM involved, 100% on every recorded run.
* ``citation_validity`` — 100% on every recorded run; a citation to a playbook
  position that doesn't exist is an invented source, not a bad judgment call.

``classification_accuracy`` and ``risk_accuracy`` are reported but not gated.
On this contract only four clauses carry a gold label, so a single clause
moves the figure by 25 points — a threshold there would fail on noise, and the
labels themselves are CUAD review categories bent into clause types (see
"ซ่อม gold label" in the repo README). Those two numbers are tracked by
running ``scripts.run_eval`` over the wider set, where the sample is large
enough for the number to mean something.
"""

from __future__ import annotations

import pytest

from app.dependencies import get_known_positions, get_orchestrator
from app.services.evaluation import format_report, run_eval

pytestmark = pytest.mark.live_llm

# The shortest contract in the gold set: 8 clauses, ~3 minutes of provider
# time. The gate is checking that the pipeline still holds its shape, and the
# full 327-clause set costs two hours to answer the same question.
CONTRACT_ID = "ticketscominc-sponsorship-agreement"

# Both metrics have measured 100% on every recorded run. The floor sits below
# that rather than at it because segmentation matches spans by IoU, and one
# clause boundary landing differently should read as drift worth looking at,
# not as a build failure on a run that is otherwise identical.
MIN_SEGMENTATION_F1 = 0.95
MIN_CITATION_VALIDITY = 1.0


def test_regression_pipeline_holds_its_shape() -> None:
    metrics = run_eval(
        "data/gold/annotations.jsonl",
        orchestrator=get_orchestrator(),
        known_position_ids=set(get_known_positions()),
        contract_ids={CONTRACT_ID},
    )

    # Printed whether or not the assertions pass: when this gate fails, the
    # first question is always which metric moved and by how much.
    print(format_report(metrics))

    assert metrics.segmentation_f1 >= MIN_SEGMENTATION_F1
    assert metrics.citation_validity >= MIN_CITATION_VALIDITY
