"""Playbook ingestion: YAML/CSV -> chunks -> embeddings -> vector store."""

from __future__ import annotations

from pathlib import Path

from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.schemas.playbook import PlaybookPosition


def load_positions(path: str | Path) -> list[PlaybookPosition]:
    """Load playbook positions from a YAML file.

    TODO: parse ``data/playbook/positions.yaml`` into PlaybookPosition models.
    """
    raise NotImplementedError


def ingest(positions: list[PlaybookPosition], embedder: Embedder, store: VectorStore) -> int:
    """Embed and upsert positions; return the number ingested.

    TODO: embed ``preferred_language``/``fallback_language`` and upsert.
    """
    raise NotImplementedError
