"""Playbook ingestion: YAML/CSV -> chunks -> embeddings -> vector store."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore
from app.schemas.playbook import PlaybookPosition


def load_positions(path: str | Path) -> list[PlaybookPosition]:
    """Load playbook positions from a YAML file."""
    raw = yaml.safe_load(Path(path).read_text())
    return [PlaybookPosition(**item) for item in (raw or {}).get("positions", [])]


def ingest(positions: list[PlaybookPosition], embedder: Embedder, store: VectorStore) -> int:
    """Embed and upsert positions; return the number ingested."""
    if not positions:
        return 0
    texts = [f"{p.title}. {p.preferred_language} {p.fallback_language}" for p in positions]
    vectors = embedder.embed(texts)
    for position, vector in zip(positions, vectors, strict=True):
        store.upsert(position, vector)
    return len(positions)
