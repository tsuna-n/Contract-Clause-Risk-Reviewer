"""Unit tests for the clause segmenter."""

from app.agents.segmenter import Segmenter
from app.parsers.models import ParsedDocument, TextSpan


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


def test_segmenter_falls_back_to_paragraphs_without_headings() -> None:
    text = "First paragraph with no numbering.\n\nSecond paragraph, still no numbering."
    clauses = Segmenter(llm=None).run(_doc(text))
    assert len(clauses) == 2
    assert clauses[0].heading is None
    assert all(text[c.span.start : c.span.end] == c.text for c in clauses)


def test_segmenter_empty_document_returns_no_clauses() -> None:
    assert Segmenter(llm=None).run(_doc("")) == []
