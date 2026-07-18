"""Unit tests for citation creation/verification."""

from app.rag.citation import make_citation, verify_citation
from app.schemas.playbook import PlaybookPosition, RetrievalHit
from app.schemas.taxonomy import ClauseType


def _hit() -> RetrievalHit:
    position = PlaybookPosition(
        id="p1",
        clause_type=ClauseType.TERMINATION,
        title="t",
        preferred_language="preferred",
        fallback_language="fallback",
    )
    return RetrievalHit(position=position, score=0.9, source="hybrid")


def test_make_citation_is_deterministic() -> None:
    hit = _hit()
    c1 = make_citation(hit, "some excerpt")
    c2 = make_citation(hit, "some excerpt")
    assert c1.citation_id == c2.citation_id
    assert c1.playbook_position_id == "p1"


def test_make_citation_differs_by_excerpt() -> None:
    hit = _hit()
    c1 = make_citation(hit, "excerpt one")
    c2 = make_citation(hit, "excerpt two")
    assert c1.citation_id != c2.citation_id


def test_verify_citation() -> None:
    citation = make_citation(_hit(), "excerpt")
    assert verify_citation(citation, {"p1", "p2"})
    assert not verify_citation(citation, {"other"})
