"""Document parsing: PDF/DOCX bytes -> normalized text + page offsets.

The offsets matter: every clause the pipeline produces carries a span back into
``ParsedDocument.text``, which is what makes citations checkable against the
source instead of trusting the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO

# --- data structures ---------------------------------------------------------


@dataclass
class TextSpan:
    """A run of text mapped back to its page and char offsets."""

    start: int
    end: int
    page: int


@dataclass
class ParsedDocument:
    """Normalized text plus the offset/page metadata needed for grounding.

    ``text`` is the normalized full-document string. ``spans`` map slices of
    ``text`` back to source pages. ``page_map`` maps a page number to the
    ``(start, end)`` char range it occupies in ``text``.
    """

    text: str
    spans: list[TextSpan] = field(default_factory=list)
    page_map: dict[int, tuple[int, int]] = field(default_factory=dict)

    def page_for_offset(self, offset: int) -> int | None:
        """Return the page number containing ``offset`` in ``text``."""
        for page, (start, end) in self.page_map.items():
            if start <= offset < end:
                return page
        return None


# --- normalization -----------------------------------------------------------

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"}
_HEADING_RE = re.compile(r"^\s*(\d+(\.\d+)*)[.)]?\s+[A-Z]")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace while keeping paragraph breaks."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def replace_ligatures(text: str) -> str:
    """Replace common typographic ligatures with ASCII equivalents."""
    for lig, repl in _LIGATURES.items():
        text = text.replace(lig, repl)
    return text


def is_heading(line: str) -> bool:
    """Heuristic: does ``line`` look like a numbered clause heading?"""
    return bool(_HEADING_RE.match(line))


def normalize(text: str) -> str:
    """Apply the full normalization pipeline."""
    return normalize_whitespace(replace_ligatures(text))


# --- file formats ------------------------------------------------------------


def parse_pdf(data: bytes) -> ParsedDocument:
    """Parse PDF bytes into a :class:`ParsedDocument`, preserving page offsets."""
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


def parse_docx(data: bytes) -> ParsedDocument:
    """Parse DOCX bytes into a :class:`ParsedDocument`.

    DOCX has no real pages, so the whole document is a single synthetic page.
    """
    from docx import Document

    document = Document(BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    text = normalize("\n\n".join(paragraphs))
    span = TextSpan(start=0, end=len(text), page=1)
    return ParsedDocument(text=text, spans=[span], page_map={1: (0, len(text))})


#: Upload extension -> parser. ``ReviewService`` rejects anything not listed.
PARSERS = {"pdf": parse_pdf, "docx": parse_docx}
