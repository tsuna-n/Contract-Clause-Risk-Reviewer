"""Text normalization: whitespace, ligatures, heading detection."""

from __future__ import annotations

import re

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
