"""Resolve explicit references without inventing sections or whole-document claims."""

from __future__ import annotations

import re
import unicodedata

from app.parsers import ParsedDocument
from app.schemas import Clause, ContractSource, Span

_NUMBER = r"\d+(?:\.\d+)*"
_HEADING = re.compile(
    rf"^(?:(?:article|section|paragraph|clause|ข้อที่|ข้อ)\s*)?\(?({_NUMBER})[.)]?(?:\s|$)",
    re.IGNORECASE,
)
_REFERENCES = re.compile(
    rf"\b(?:sections?|paragraphs?|clauses?|articles?)\s+({_NUMBER})"
    rf"(?:\s*(?:,|and|&)\s*({_NUMBER}))?",
    re.IGNORECASE,
)
_THAI_REFERENCES = re.compile(rf"ข้อ(?:ที่)?\s*({_NUMBER})")
_APPENDICES = re.compile(
    r"^[ \t]*(appendix|schedule|exhibit)[ \t]*([A-Za-z0-9]+)[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
_APPENDIX_REFERENCES = re.compile(
    r"\b(appendix|schedule|exhibit)\s*([A-Za-z0-9]+)\b", re.IGNORECASE
)


def _number(value: str) -> str:
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)


class ContractContext:
    """Read-only index shared by clause workers; no model or database calls."""

    def __init__(self, document: ParsedDocument, clauses: list[Clause]) -> None:
        self.document = document
        self.sections: dict[str, list[tuple[int, int]]] = {}
        headings = [
            _HEADING.match(clause.heading.strip()) if clause.heading else None for clause in clauses
        ]
        numbers = [_number(match[1]) if match else None for match in headings]
        for index, clause in enumerate(clauses):
            key = numbers[index]
            if key is None:
                continue
            end = clause.span.end
            # A reference to Section 7 includes its 7.1, 7.2, ... subsections.
            for descendant in range(index + 1, len(clauses)):
                child = numbers[descendant]
                if child is None or not child.startswith(key + "."):
                    break
                end = clauses[descendant].span.end
            self.sections.setdefault(key, []).append((clause.span.start, end))

        self.appendices: dict[str, list[tuple[int, int]]] = {}
        matches = list(_APPENDICES.finditer(document.text))
        for index, match in enumerate(matches):
            key = f"{match[1].lower()} {match[2].upper()}"
            end = matches[index + 1].start() if index + 1 < len(matches) else len(document.text)
            self.appendices.setdefault(key, []).append((match.start(), end))

    def sources_for(self, clause: Clause) -> list[ContractSource]:
        references = []
        for match in _REFERENCES.finditer(clause.text):
            for key in match.groups():
                if key:
                    key = _number(key)
                    references.append((match.start(), f"Section {key}", self.sections.get(key, [])))
        for match in _THAI_REFERENCES.finditer(clause.text):
            key = _number(match[1])
            references.append((match.start(), f"Section {key}", self.sections.get(key, [])))
        for match in _APPENDIX_REFERENCES.finditer(clause.text):
            key = f"{match[1].lower()} {match[2].upper()}"
            references.append((match.start(), key.title(), self.appendices.get(key, [])))

        sources = []
        remaining = 5000
        for _, label, ranges in sorted(references):
            # Repeated numbering across appendices is ambiguous. Never guess.
            if len(ranges) != 1:
                continue
            start, full_end = ranges[0]
            if clause.span.start <= start and full_end <= clause.span.end:
                continue
            end = min(full_end, start + min(3500, remaining))
            truncated = end < full_end
            raw = self.document.text[start:end]
            text = raw.strip()
            if not text:
                continue
            start += len(raw) - len(raw.lstrip())
            end = start + len(text)
            if any(source.span.start <= start and end <= source.span.end for source in sources):
                continue
            sources.append(
                ContractSource(
                    label=label,
                    text=text,
                    truncated=truncated,
                    span=Span(start=start, end=end, page=self.document.page_for_offset(start)),
                )
            )
            remaining -= len(text)
            if len(sources) >= 3 or remaining <= 0:
                break
        return sources
