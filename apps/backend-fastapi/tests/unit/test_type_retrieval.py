"""Subject-specific retrieval must retain policies missing from the global pool."""

import pytest

from app.ai.retrieval import DummyEmbedder, Retriever
from app.config import get_settings
from app.schemas import Clause, ClauseType, PlaybookPosition, RetrievalHit, Span


def hit(key, subject=ClauseType.CONFIDENTIALITY, score=0.9):
    return RetrievalHit(
        position=PlaybookPosition(
            id=key,
            title=key,
            clause_type=subject,
            preferred_language="Either party shall give written notice before termination.",
            fallback_language="The parties shall cooperate upon notice of termination.",
        ),
        score=score,
    )


class GlobalStore:
    def query(self, vector, top_k=5):
        return [hit(f"global-{i}") for i in range(min(10, top_k))]


def test_policies_containing_only_stopwords_do_not_fail_retrieval():
    candidate = hit("stopwords")
    candidate.position.title = "The agreement"
    candidate.position.preferred_language = "The party shall."
    candidate.position.fallback_language = ""
    assert Retriever._bm25_scores("notice", [candidate]) == [0.0]


class TypedStore(GlobalStore):
    def __init__(self):
        self.calls = []

    def query_by_type(self, vector, clause_type, top_k=2):
        self.calls.append((clause_type, top_k))
        return [hit("wind-down", clause_type, 0.5), hit("cure", clause_type, 0.45)][:top_k]


@pytest.mark.parametrize("top_k", [1, 5])
def test_relevant_subject_policies_survive_a_stronger_unrelated_global_pool(monkeypatch, top_k):
    monkeypatch.setattr(get_settings(), "enable_hybrid_retrieval", True)
    store = TypedStore()
    clause = Clause(
        id="c1",
        text="Three months sell-off after termination.",
        clause_type=ClauseType.TERMINATION,
        span=Span(start=0, end=40),
    )
    results = Retriever(DummyEmbedder(), store).retrieve(clause, top_k=top_k)
    assert len(results) == top_k
    assert "wind-down" in {r.position.id for r in results}
    if top_k == 5:
        assert "cure" in {r.position.id for r in results}
        assert sum(r.position.clause_type != ClauseType.TERMINATION for r in results) == 3


def test_other_subject_and_legacy_stores_keep_global_retrieval(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_hybrid_retrieval", True)
    clause = Clause(id="c1", text="Notice of severability.", span=Span(start=0, end=23))
    store = TypedStore()
    assert len(Retriever(DummyEmbedder(), store).retrieve(clause, top_k=5)) == 5
    assert not store.calls
    clause.clause_type = ClauseType.TERMINATION
    assert len(Retriever(DummyEmbedder(), GlobalStore()).retrieve(clause, top_k=5)) == 5


def test_global_and_subject_duplicates_do_not_take_extra_slots(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_hybrid_retrieval", True)

    class OverlappingStore(TypedStore):
        def query(self, vector, top_k=5):
            return [hit("wind-down", ClauseType.TERMINATION), *super().query(vector, top_k)]

    clause = Clause(
        id="c1",
        text="Termination notice.",
        clause_type=ClauseType.TERMINATION,
        span=Span(start=0, end=19),
    )
    results = Retriever(DummyEmbedder(), OverlappingStore()).retrieve(clause, top_k=5)
    assert len({r.position.id for r in results}) == len(results) == 5


def test_negative_relevance_scores_do_not_become_positive_evidence(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_hybrid_retrieval", True)

    class NegativeStore:
        def query(self, vector, top_k=5):
            return [hit("less-irrelevant", score=-0.1), hit("very-irrelevant", score=-0.9)]

    retriever = Retriever(DummyEmbedder(), NegativeStore())
    monkeypatch.setattr(retriever, "_bm25_scores", lambda text, candidates: [-0.1, -0.8])
    clause = Clause(id="c1", text="Unrelated subject.", span=Span(start=0, end=18))
    assert all(item.score == 0 for item in retriever.retrieve(clause))


def test_default_pool_retains_wind_down_and_secondary_subjects(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_hybrid_retrieval", True)

    class TerminationStore(GlobalStore):
        def query_by_type(self, vector, clause_type, top_k=2):
            return [
                hit("convenience", clause_type, 0.83),
                hit("cure", clause_type, 0.82),
                hit("wind-down", clause_type, 0.81),
                hit("renewal", clause_type, 0.79),
            ][:top_k]

    clause = Clause(
        id="c1",
        text="After termination, three months sell-off.",
        clause_type=ClauseType.TERMINATION,
        span=Span(start=0, end=40),
    )
    results = Retriever(DummyEmbedder(), TerminationStore()).retrieve(clause)
    assert len(results) == 8
    assert "wind-down" in {item.position.id for item in results}
    assert any(item.position.clause_type != ClauseType.TERMINATION for item in results)
