"""Unit tests for the clause segmenter."""

from app.ai.agents import Segmenter
from app.parsers import ParsedDocument, TextSpan


def _doc(text: str) -> ParsedDocument:
    return ParsedDocument(
        text=text,
        spans=[TextSpan(start=0, end=len(text), page=1)],
        page_map={1: (0, len(text))},
    )


def test_segmenter_splits_on_numbered_headings() -> None:
    text = (
        "1. Confidentiality.\nEach party shall keep information secret.\n\n"
        "2. Termination.\nEither party may terminate upon notice."
    )
    clauses = Segmenter(llm=None).run(_doc(text))
    assert [c.heading for c in clauses] == ["1. Confidentiality.", "2. Termination."]
    assert clauses[0].span.start == 0
    assert clauses[0].span.end == clauses[1].span.start
    assert text[clauses[1].span.start : clauses[1].span.end] == clauses[1].text


def test_segmenter_splits_thai_contract_on_headings() -> None:
    """A Thai contract splits on its clauses, not on its paragraph breaks.

    The distinction matters: before the heading rule understood Thai, this
    document fell through to the paragraph fallback and every blank line
    started a new "clause", so clause boundaries had nothing to do with the
    agreement's own numbering.
    """
    text = (
        "ข้อ 1. การรักษาความลับ\n"
        "คู่สัญญาแต่ละฝ่ายตกลงเก็บรักษาข้อมูลอันเป็นความลับของอีกฝ่ายหนึ่ง\n\n"
        "ทั้งนี้ให้มีผลต่อไปอีกสามปีนับแต่วันสิ้นสุดสัญญา\n\n"
        "ข้อ 2. การเลิกสัญญา\n"
        "คู่สัญญาฝ่ายใดฝ่ายหนึ่งอาจบอกเลิกสัญญาโดยบอกกล่าวล่วงหน้าสามสิบวัน"
    )
    clauses = Segmenter(llm=None).run(_doc(text))

    assert [c.heading for c in clauses] == ["ข้อ 1. การรักษาความลับ", "ข้อ 2. การเลิกสัญญา"]
    # The blank line inside clause 1 stays inside it.
    assert "ทั้งนี้ให้มีผลต่อไปอีกสามปี" in clauses[0].text
    # Each span still points at the clause it came from. Compared after
    # stripping because a span runs to the next heading and so takes the blank
    # line before it with it, while ``text`` is stored trimmed.
    assert all(text[c.span.start : c.span.end].strip() == c.text for c in clauses)


def test_segmenter_falls_back_to_paragraphs_without_headings() -> None:
    text = "First paragraph with no numbering.\n\nSecond paragraph, still no numbering."
    clauses = Segmenter(llm=None).run(_doc(text))
    assert len(clauses) == 2
    assert clauses[0].heading is None
    assert all(text[c.span.start : c.span.end] == c.text for c in clauses)


def test_segmenter_empty_document_returns_no_clauses() -> None:
    assert Segmenter(llm=None).run(_doc("")) == []
