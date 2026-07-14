"""PDF parsing via PyMuPDF, preserving page + char offsets."""

from __future__ import annotations

from app.parsers.models import ParsedDocument


def parse_pdf(data: bytes) -> ParsedDocument:
    """Parse PDF bytes into a :class:`ParsedDocument`.

    TODO: use ``fitz`` (PyMuPDF) to extract per-page text, accumulate the
    global offset, and build ``page_map`` / ``spans``.
    """
    # import fitz  # PyMuPDF - imported lazily once implemented
    raise NotImplementedError
