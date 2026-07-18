"""PDF parsing via PyMuPDF, preserving page + char offsets."""

from __future__ import annotations

from app.parsers.models import ParsedDocument, TextSpan
from app.parsers.normalizer import normalize


def parse_pdf(data: bytes) -> ParsedDocument:
    """Parse PDF bytes into a :class:`ParsedDocument`."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        raw_pages = [page.get_text() for page in doc]
    finally:
        doc.close()

    text_parts: list[str] = []
    spans: list[TextSpan] = []
    page_map: dict[int, tuple[int, int]] = {}
    offset = 0
    for page_number, raw_text in enumerate(raw_pages, start=1):
        page_text = normalize(raw_text)
        if not page_text:
            continue
        if text_parts:
            text_parts.append("\n\n")
            offset += 2
        start = offset
        text_parts.append(page_text)
        offset += len(page_text)
        spans.append(TextSpan(start=start, end=offset, page=page_number))
        page_map[page_number] = (start, offset)

    return ParsedDocument(text="".join(text_parts), spans=spans, page_map=page_map)
