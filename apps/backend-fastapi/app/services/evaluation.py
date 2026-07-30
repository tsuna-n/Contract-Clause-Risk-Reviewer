"""Evaluation harness: run the gold set through the pipeline and score it.

Metrics, the runner, and the text report live together because they are only
ever used together — by ``POST /evaluate``, ``scripts/run_eval.py``, and the
regression gate in ``tests/eval``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ai.pipeline import Orchestrator
from app.errors import InvalidInputError
from app.logger import get_logger
from app.parsers import ParsedDocument, TextSpan, normalize
from app.schemas import EvalMetrics, EvalRequest, PerTypeMetrics, Span

logger = get_logger(__name__)

#: Where a gold set is allowed to live. ``gold_set_path`` arrives in the request
#: body, so without this the endpoint reads any file the process can — and
#: reports back through parse errors what it found there.
GOLD_SET_ROOT = Path("data/gold")


def resolve_gold_set_path(raw: str) -> str:
    """Return ``raw`` as a path inside :data:`GOLD_SET_ROOT`, or refuse it.

    Resolved before comparing, so ``data/gold/../../.env`` is rejected on what
    it points at rather than on how it is spelled.
    """
    root = GOLD_SET_ROOT.resolve()
    candidate = Path(raw).resolve()
    if candidate != root and root not in candidate.parents:
        raise InvalidInputError(
            f"gold_set_path must be inside {GOLD_SET_ROOT}/ (got {raw!r})"
        )
    return str(candidate)


# --- metrics -----------------------------------------------------------------


def span_iou(a: Span, b: Span) -> float:
    """Intersection-over-union of two character spans."""
    inter = max(0, min(a.end, b.end) - max(a.start, b.start))
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def segmentation_f1(
    predicted: list[Span],
    gold: list[Span],
    iou_threshold: float = 0.5,
) -> float:
    """Span-IoU F1 for clause segmentation.

    Greedily matches each predicted span to its best unmatched gold span
    above ``iou_threshold``, then computes precision/recall/F1.
    """
    if not predicted and not gold:
        return 1.0
    if not predicted or not gold:
        return 0.0

    remaining = list(gold)
    matches = 0
    for pred in predicted:
        best_idx, best_iou = None, 0.0
        for idx, candidate in enumerate(remaining):
            iou = span_iou(pred, candidate)
            if iou >= iou_threshold and iou > best_iou:
                best_idx, best_iou = idx, iou
        if best_idx is not None:
            matches += 1
            del remaining[best_idx]

    precision = matches / len(predicted)
    recall = matches / len(gold)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def accuracy(predicted: list[str], gold: list[str]) -> float:
    """Simple label accuracy over aligned prediction/gold lists."""
    if not gold:
        return 0.0
    correct = sum(p == g for p, g in zip(predicted, gold, strict=True))
    return correct / len(gold)


def citation_validity_rate(valid: int, total: int) -> float:
    """Fraction of citations that reference a real playbook position."""
    return valid / total if total else 0.0


# --- runner ------------------------------------------------------------------


def load_gold(path: str | Path) -> list[dict]:
    """Load gold annotations from a JSONL file."""
    records = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _load_contract_text(gold_path: str | Path, contract_id: str) -> str | None:
    """Return the raw fixture text for ``contract_id``, or ``None`` if missing."""
    contracts_dir = Path(gold_path).resolve().parent.parent / "contracts"
    contract_path = contracts_dir / f"{contract_id}.txt"
    return contract_path.read_text() if contract_path.exists() else None


def run_eval(
    gold_path: str | Path,
    *,
    orchestrator: Orchestrator,
    known_position_ids: set[str],
    limit: int | None = None,
    contract_ids: set[str] | None = None,
) -> EvalMetrics:
    """Run ``orchestrator`` over the gold set and return aggregate metrics.

    The eval regression gate requires >= 75% accuracy (see tests/eval). Gold
    records whose ``data/contracts/<contract_id>.txt`` fixture is missing are
    skipped (logged, not failed) so the harness degrades gracefully.

    ``limit`` and ``contract_ids`` both narrow the run, and exist because the
    full set is roughly 1,300 LLM calls: ``limit`` takes the first N records,
    ``contract_ids`` picks named ones — which is how you run the *cheap*
    contracts rather than whichever happen to be first in the file.
    """
    records = load_gold(gold_path)
    if contract_ids is not None:
        records = [record for record in records if record["contract_id"] in contract_ids]
    if limit is not None:
        records = records[:limit]

    pred_spans: list[Span] = []
    gold_spans: list[Span] = []
    pred_types: list[str] = []
    gold_types: list[str] = []
    pred_risks: list[str] = []
    gold_risks: list[str] = []
    valid_citations = 0
    total_citations = 0

    for record in records:
        contract_id = record["contract_id"]
        raw_text = _load_contract_text(gold_path, contract_id)
        if raw_text is None:
            logger.warning("run_eval: no contract fixture for %s, skipping", contract_id)
            continue

        text = normalize(raw_text)
        document = ParsedDocument(
            text=text,
            spans=[TextSpan(start=0, end=len(text), page=1)],
            page_map={1: (0, len(text))},
        )
        report = orchestrator.review(document, contract_id=contract_id, session_id="eval")

        gold_clauses = record.get("clauses", [])
        record_gold_spans = [Span(**clause["span"]) for clause in gold_clauses]
        gold_spans.extend(record_gold_spans)
        pred_spans.extend(review.clause.span for review in report.reviews)

        for gold_clause, gold_span in zip(gold_clauses, record_gold_spans, strict=True):
            # A gold clause may carry a boundary but no label: the fixtures are
            # built from CUAD, whose 41 categories don't span the whole
            # taxonomy, and inventing a label for the rest would score the
            # pipeline against guesses. Those clauses still count towards
            # segmentation - they are real clause boundaries - and are simply
            # not classification/risk samples.
            if "clause_type" not in gold_clause:
                continue
            match = max(
                report.reviews,
                key=lambda r: span_iou(r.clause.span, gold_span),
                default=None,
            )
            if match is None:
                continue
            gold_types.append(gold_clause["clause_type"])
            pred_types.append(match.clause.clause_type.value)
            gold_risks.append(gold_clause["risk_level"])
            pred_risks.append(match.risk_level.value)

        for review in report.reviews:
            for citation in review.citations:
                total_citations += 1
                if citation.playbook_position_id in known_position_ids:
                    valid_citations += 1

    per_type_hits: dict[str, list[bool]] = {}
    for gold_type, pred_type in zip(gold_types, pred_types, strict=True):
        per_type_hits.setdefault(gold_type, []).append(gold_type == pred_type)

    return EvalMetrics(
        segmentation_f1=segmentation_f1(pred_spans, gold_spans),
        classification_accuracy=accuracy(pred_types, gold_types),
        risk_accuracy=accuracy(pred_risks, gold_risks),
        citation_validity=citation_validity_rate(valid_citations, total_citations),
        per_type=[
            PerTypeMetrics(clause_type=t, support=len(hits), accuracy=sum(hits) / len(hits))
            for t, hits in per_type_hits.items()
        ],
        classification_confusion=confusion_matrix(pred_types, gold_types),
    )


# --- reporting ---------------------------------------------------------------


def confusion_matrix(predicted: list[str], gold: list[str]) -> dict[str, dict[str, int]]:
    """Build a nested ``gold -> predicted -> count`` confusion matrix."""
    matrix: dict[str, dict[str, int]] = {}
    for pred, actual in zip(predicted, gold, strict=True):
        matrix.setdefault(actual, {})
        matrix[actual][pred] = matrix[actual].get(pred, 0) + 1
    return matrix


def format_report(metrics: EvalMetrics) -> str:
    """Render metrics as a human-readable text report."""
    lines = [
        "Evaluation report",
        "==================",
        f"segmentation_f1:          {metrics.segmentation_f1:.2%}",
        f"classification_accuracy:  {metrics.classification_accuracy:.2%}",
        f"risk_accuracy:            {metrics.risk_accuracy:.2%}",
        f"citation_validity:        {metrics.citation_validity:.2%}",
    ]
    if metrics.per_type:
        lines.append("")
        lines.append("Per clause type (classification):")
        for row in metrics.per_type:
            lines.append(f"  {row.clause_type:<28} n={row.support:<4} acc={row.accuracy:.2%}")
    if metrics.classification_confusion:
        lines.append("")
        # Printed because the aggregate hides which way the disagreements go,
        # and that is the whole diagnosis: a gold set built from CUAD carries
        # the label of whichever annotation fell inside the clause, so a clause
        # headed "13. Warranty" whose only annotation is ``Insurance`` is gold
        # ``other``. Reading 57% as "the classifier is 57% right" is a mistake
        # this block exists to make harder.
        lines.append("Where classification disagreed (gold -> predicted, n):")
        for gold, predictions in sorted(metrics.classification_confusion.items()):
            wrong = {
                predicted: count for predicted, count in predictions.items() if predicted != gold
            }
            if wrong:
                pairs = ", ".join(f"{p} ({c})" for p, c in sorted(wrong.items()))
                lines.append(f"  {gold:<28} -> {pairs}")
    return "\n".join(lines)


# --- service -----------------------------------------------------------------


class EvalService:
    """Runs the evaluation harness and returns aggregate metrics."""

    def __init__(self, orchestrator: Orchestrator, known_position_ids: set[str]) -> None:
        self.orchestrator = orchestrator
        self.known_position_ids = known_position_ids

    def run(self, request: EvalRequest) -> EvalMetrics:
        """Evaluate the pipeline against a gold set."""
        return run_eval(
            resolve_gold_set_path(request.gold_set_path),
            orchestrator=self.orchestrator,
            known_position_ids=self.known_position_ids,
            limit=request.limit,
        )
