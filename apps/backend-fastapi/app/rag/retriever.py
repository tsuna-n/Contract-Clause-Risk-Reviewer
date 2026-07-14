"""Hybrid retrieval: BM25 + dense, with optional rerank."""

from __future__ import annotations

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

        TODO: run dense query via the vector store, blend with a BM25 lexical
        score, dedupe, rerank, and return the top_k hits.
        """
        raise NotImplementedError
