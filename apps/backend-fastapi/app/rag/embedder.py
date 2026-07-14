"""Embedding provider abstraction."""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """Turns text into dense vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class DummyEmbedder:
    """Placeholder embedder used until a real provider is wired up."""

    dim = 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        """TODO: replace with a real embedding backend."""
        raise NotImplementedError
