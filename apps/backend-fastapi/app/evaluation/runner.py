"""Evaluation runner: execute the gold set and compute metrics."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.orchestrator import Orchestrator
from app.core.logging import get_logger
from app.evaluation.metrics import accuracy, citation_validity_rate, segmentation_f1, span_iou
from app.parsers.models import ParsedDocument, TextSpan
from app.parsers.normalizer import normalize
from app.schemas.clause import Span
from app.schemas.eval import EvalMetrics, PerTypeMetrics

logger = get_logger(__name__)


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
) -> EvalMetrics:
    """Run ``orchestrator`` over the gold set and return aggregate metrics.

    The eval regression gate requires >= 75% accuracy (see tests/eval). Gold
    records whose ``data/contracts/<contract_id>.txt`` fixture is missing are
    skipped (logged, not failed) so the harness degrades gracefully.
    """
    records = load_gold(gold_path)
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
    )
