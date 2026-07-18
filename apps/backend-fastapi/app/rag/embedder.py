"""Embedding provider abstraction."""

from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.config import get_settings


class Embedder(Protocol):
    """Turns text into dense vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class GeminiEmbedder:
    """Embedder backed by the Google GenAI (Gemini) embedding API."""

    def __init__(self, model: str | None = None, dim: int | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self.dim = dim or settings.embedding_dim
        self._api_key = settings.gemini_api_key
        self._client = None  # lazily constructed google.genai.Client

    def _get_client(self):
        """Lazily construct the underlying ``google.genai.Client``."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        if not texts:
            return []
        from google.genai import types

        response = self._get_client().models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dim,
            ),
        )
        return [list(embedding.values or []) for embedding in response.embeddings or []]


class DummyEmbedder:
    """Deterministic, network-free embedder used in tests and offline scripts."""

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Hash each text into a fixed-size pseudo-embedding."""
        vectors: list[list[float]] = []
        for text in texts:
            values: list[float] = []
            block = text.encode("utf-8")
            while len(values) < self.dim:
                block = hashlib.sha256(block).digest()
                values.extend(b / 255.0 for b in block)
            vectors.append(values[: self.dim])
        return vectors
