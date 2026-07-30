"""Contract-level metadata extraction, and the grounding rule it lives under.

The LLM is stubbed: what is under test is not whether a model can read a
preamble, it is what the extractor does with the answer. Metadata is the part
of a report that reads like a transcription — a reviewer who would question a
risk rating will not question a party name — so anything the model returns
that isn't in the document word-for-word has to be thrown away rather than
displayed.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.ai.agents import (
    _METADATA_HEAD_CHARS,
    _METADATA_TAIL_CHARS,
    MetadataExtractor,
    _metadata_excerpt,
)
from app.ai.pipeline import Orchestrator
from app.parsers import ParsedDocument
from app.schemas import ContractMetadata

CONTRACT = (
    "SERVICES AGREEMENT\n\n"
    "This Services Agreement is made as of March 3, 2019 between "
    "Acme Corporation, a Delaware corporation, and Globex Limited.\n\n"
    "1. Fees. The total fee payable is $1,200,000.\n\n"
    "12. Governing Law. This Agreement is governed by the laws of the State of New York.\n"
)


class StubLLM:
    """Returns one canned :class:`ContractMetadata`, whatever it is asked."""

    def __init__(self, answer: ContractMetadata) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def complete_structured(self, *, system: str, prompt: str, response_model: Any, **_: Any):
        self.prompts.append(prompt)
        return self.answer


def extract(answer: ContractMetadata, text: str = CONTRACT) -> ContractMetadata:
    extractor = MetadataExtractor(StubLLM(answer))  # type: ignore[arg-type]
    return extractor.run(ParsedDocument(text=text))


def test_keeps_values_quoted_from_the_document() -> None:
    result = extract(
        ContractMetadata(
            parties=["Acme Corporation", "Globex Limited"],
            agreement_date="March 3, 2019",
            contract_value="$1,200,000",
            governing_law="the laws of the State of New York",
        )
    )

    assert result.parties == ["Acme Corporation", "Globex Limited"]
    assert result.agreement_date == "March 3, 2019"
    assert result.contract_value == "$1,200,000"
    assert result.governing_law == "the laws of the State of New York"


def test_drops_a_value_the_document_never_states() -> None:
    """The failure mode this guards: a confident, plausible, invented figure."""
    result = extract(ContractMetadata(contract_value="$2,500,000"))

    assert result.contract_value is None


def test_drops_only_the_ungrounded_parties() -> None:
    result = extract(ContractMetadata(parties=["Acme Corporation", "Initech LLC"]))

    assert result.parties == ["Acme Corporation"]


def test_a_reformatted_date_is_not_grounded() -> None:
    """An ISO date is the same day, but it is not what the contract says."""
    result = extract(ContractMetadata(agreement_date="2019-03-03"))

    assert result.agreement_date is None


def test_matching_ignores_whitespace_and_case() -> None:
    """A line break inside a quoted name is the PDF's, not the model's."""
    result = extract(ContractMetadata(parties=["acme    corporation"]))

    assert result.parties == ["acme    corporation"]


def test_empty_metadata_reports_itself_as_empty() -> None:
    assert extract(ContractMetadata(parties=["Nobody Inc"])).is_empty()
    assert not extract(ContractMetadata(parties=["Globex Limited"])).is_empty()


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_values_are_normalized_to_none(blank: str) -> None:
    assert extract(ContractMetadata(effective_date=blank)).effective_date is None


# --- in the pipeline ----------------------------------------------------------


class _NoClauses:
    """A segmenter that finds nothing, so no clause agents are reached."""

    def run(self, _: ParsedDocument) -> list:
        return []


class _Unavailable:
    def run(self, _: ParsedDocument) -> ContractMetadata:
        raise RuntimeError("model unavailable")


def _orchestrator(metadata_extractor: Any) -> Orchestrator:
    return Orchestrator(
        segmenter=_NoClauses(),  # type: ignore[arg-type]
        classifier=None,  # type: ignore[arg-type]
        matcher=None,  # type: ignore[arg-type]
        risk_scorer=None,  # type: ignore[arg-type]
        judge=None,  # type: ignore[arg-type]
        metadata_extractor=metadata_extractor,
    )


def test_a_failed_extraction_costs_the_header_not_the_report() -> None:
    """A review takes minutes and real money; missing parties must not void it."""
    report = _orchestrator(_Unavailable()).review(
        ParsedDocument(text=CONTRACT), contract_id="c1", session_id="s1"
    )

    assert report.metadata.is_empty()
    assert report.disclaimer  # the report is otherwise intact


def test_extraction_can_be_switched_off_entirely() -> None:
    report = _orchestrator(None).review(
        ParsedDocument(text=CONTRACT), contract_id="c1", session_id="s1"
    )

    assert report.metadata.is_empty()


# --- what the model is shown --------------------------------------------------


def test_short_documents_are_sent_whole() -> None:
    assert _metadata_excerpt(CONTRACT) == CONTRACT


def test_long_documents_are_sent_as_opening_plus_closing() -> None:
    """Governing law and the term sit at the end; the middle is clause text."""
    body = "x" * 10 * (_METADATA_HEAD_CHARS + _METADATA_TAIL_CHARS)
    text = f"PREAMBLE{body}GOVERNING LAW"

    excerpt = _metadata_excerpt(text)

    assert excerpt.startswith("PREAMBLE")
    assert excerpt.endswith("GOVERNING LAW")
    assert "omitted" in excerpt
    # An order of magnitude smaller: the middle of a long contract is never
    # sent, which is the point of reading only the two ends.
    assert len(excerpt) < len(text) / 5
