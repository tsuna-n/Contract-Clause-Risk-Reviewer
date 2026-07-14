"""Citation id creation + existence verification."""

from __future__ import annotations

import hashlib

from app.schemas.clause import Citation
from app.schemas.playbook import RetrievalHit


def make_citation(hit: RetrievalHit, excerpt: str) -> Citation:
    """Build a deterministic :class:`Citation` for a retrieval hit."""
    raw = f"{hit.position.id}:{excerpt}".encode()
    citation_id = hashlib.sha1(raw).hexdigest()[:12]  # noqa: S324 - non-security id
    return Citation(
        citation_id=citation_id,
        playbook_position_id=hit.position.id,
        excerpt=excerpt,
    )


def verify_citation(citation: Citation, known_position_ids: set[str]) -> bool:
    """Return ``True`` if the citation points at a real playbook position."""
    return citation.playbook_position_id in known_position_ids
