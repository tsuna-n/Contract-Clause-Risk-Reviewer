"""Hybrid retrieval: BM25 + dense, with optional rerank."""

from __future__ import annotations

from app.core.config import get_settings
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.schemas.clause import Clause
from app.schemas.playbook import RetrievalHit


class Retriever:
    """Retrieves playbook positions relevant to a clause."""

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def retrieve(self, clause: Clause, top_k: int = 5) -> list[RetrievalHit]:
        """Return the top playbook positions for ``clause``.

        Runs a dense query via the vector store, then (when hybrid retrieval
        is enabled) reranks the candidate pool with a BM25 lexical score
        blended 50/50 with the normalized dense score.
        """
        settings = get_settings()
        (vector,) = self.embedder.embed([clause.text])

        if not settings.enable_hybrid_retrieval:
            return self.store.query(vector, top_k=top_k)

        candidates = self.store.query(vector, top_k=max(top_k * 4, top_k))
        if not candidates:
            return []

        bm25_scores = self._bm25_scores(clause.text, candidates)
        dense_scores = [hit.score for hit in candidates]
        max_dense = max(dense_scores) or 1.0
        max_bm25 = max(bm25_scores) or 1.0

        seen: set[str] = set()
        blended: list[RetrievalHit] = []
        for hit, dense, bm25 in zip(candidates, dense_scores, bm25_scores, strict=True):
            if hit.position.id in seen:
                continue
            seen.add(hit.position.id)
            score = 0.5 * (dense / max_dense) + 0.5 * (bm25 / max_bm25)
            blended.append(RetrievalHit(position=hit.position, score=score, source="hybrid"))

        blended.sort(key=lambda hit: hit.score, reverse=True)
        return blended[:top_k]

    @staticmethod
    def _bm25_scores(query_text: str, candidates: list[RetrievalHit]) -> list[float]:
        """Score each candidate's playbook text against ``query_text`` via BM25."""
        from rank_bm25 import BM25Okapi

        corpus = [
            f"{hit.position.title} {hit.position.preferred_language} "
            f"{hit.position.fallback_language}".lower().split()
            for hit in candidates
        ]
        bm25 = BM25Okapi(corpus)
        return list(bm25.get_scores(query_text.lower().split()))
