"""Unit tests for PDF/DOCX parsing."""

from io import BytesIO

from app.parsers.docx import parse_docx
from app.parsers.pdf import parse_pdf


def test_parse_pdf_extracts_text_and_page_map() -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. Confidentiality.")
    data = doc.write()
    doc.close()

    parsed = parse_pdf(data)
    assert "Confidentiality" in parsed.text
    assert parsed.page_map[1] == (0, len(parsed.text))
    assert parsed.page_for_offset(0) == 1


def test_parse_docx_joins_paragraphs_as_single_page() -> None:
    from docx import Document

    document = Document()
    document.add_paragraph("1. Confidentiality.")
    document.add_paragraph("Each party shall keep information secret.")
    buf = BytesIO()
    document.save(buf)

    parsed = parse_docx(buf.getvalue())
    assert "Confidentiality" in parsed.text
    assert "secret" in parsed.text
    assert parsed.page_map == {1: (0, len(parsed.text))}
