"""DOCX parsing via python-docx."""

from __future__ import annotations

from app.parsers.models import ParsedDocument


def parse_docx(data: bytes) -> ParsedDocument:
    """Parse DOCX bytes into a :class:`ParsedDocument`.

    TODO: use ``docx.Document`` over a ``BytesIO`` wrapper, join paragraph
    runs, and track offsets. DOCX has no real pages, so page_map is a single
    synthetic page.
    """
    # from docx import Document  # imported lazily once implemented
    raise NotImplementedError
