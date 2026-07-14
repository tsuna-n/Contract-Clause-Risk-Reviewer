"""Parsed-document data structures."""

from __future__ import annotations

from dataclasses import dataclass, field


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
