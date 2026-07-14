"""Vector store adapter interface (pgvector / Qdrant)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.playbook import PlaybookPosition, RetrievalHit


class VectorStore(Protocol):
    """Storage + similarity search over playbook chunks."""

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """Insert or update a position's vector."""
        ...

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """Return the ``top_k`` nearest positions to ``vector``."""
        ...


class PgVectorStore:
    """pgvector-backed :class:`VectorStore` implementation."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """TODO: upsert into a pgvector table."""
        raise NotImplementedError

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """TODO: run a ``<=>`` cosine-distance query."""
        raise NotImplementedError
