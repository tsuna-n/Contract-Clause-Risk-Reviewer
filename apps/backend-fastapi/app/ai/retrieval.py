"""Grounded RAG: embed -> store -> retrieve -> cite.

One module for the whole retrieval side, in the order data flows through it:
playbook YAML is embedded and upserted into pgvector (``ingest``), a clause is
embedded and matched against it (:class:`Retriever`), and the winning positions
become citations (:func:`make_citation`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import yaml
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import SessionLocal
from app.models import PlaybookEmbedding
from app.schemas import (
    Citation,
    Clause,
    ClauseType,
    PlaybookPosition,
    RetrievalHit,
    RetrievalSource,
    RiskLevel,
)

# --- embedding ---------------------------------------------------------------


class Embedder(Protocol):
    """Turns text into dense vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...


class GeminiEmbedder:
    """Embedder backed by the Google GenAI (Gemini) embedding API."""

    def __init__(
        self,
        model: str | None = None,
        dim: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self.dim = dim or settings.embedding_dim
        self._api_key = settings.gemini_api_key
        self._timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self._client = None  # lazily constructed google.genai.Client

    def _get_client(self):
        """Lazily construct the underlying ``google.genai.Client``."""
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key,
                # HttpOptions.timeout is milliseconds.
                http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            )
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


# --- vector store ------------------------------------------------------------


class VectorStore(Protocol):
    """Storage + similarity search over playbook chunks."""

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """Insert or update a position's vector."""
        ...

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """Return the ``top_k`` nearest positions to ``vector``."""
        ...

    def list_all(self) -> list[PlaybookPosition]:
        """Return every stored position.

        The judge needs this: it has to recognise any position the retriever
        could hand it, and the retriever reads the store, not the seed YAML.
        """
        ...


class PgVectorStore:
    """pgvector-backed :class:`VectorStore` implementation.

    Reads and writes :class:`~app.models.PlaybookEmbedding` through the app's
    shared session factory (see ``app/database.py``).
    """

    def __init__(self, session_factory=SessionLocal) -> None:  # noqa: ANN001 - sessionmaker
        self._session_factory = session_factory

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """Upsert ``position`` and its embedding into ``playbook_embeddings``."""
        stmt = insert(PlaybookEmbedding).values(
            id=position.id,
            clause_type=position.clause_type.value,
            title=position.title,
            preferred_language=position.preferred_language,
            fallback_language=position.fallback_language,
            risk_if_absent=position.risk_if_absent.value,
            tags=position.tags,
            embedding=vector,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PlaybookEmbedding.id],
            set_={
                "clause_type": stmt.excluded.clause_type,
                "title": stmt.excluded.title,
                "preferred_language": stmt.excluded.preferred_language,
                "fallback_language": stmt.excluded.fallback_language,
                "risk_if_absent": stmt.excluded.risk_if_absent,
                "tags": stmt.excluded.tags,
                "embedding": stmt.excluded.embedding,
            },
        )
        with self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    @staticmethod
    def _to_position(row: PlaybookEmbedding) -> PlaybookPosition:
        return PlaybookPosition(
            id=row.id,
            clause_type=ClauseType(row.clause_type),
            title=row.title,
            preferred_language=row.preferred_language,
            fallback_language=row.fallback_language,
            risk_if_absent=RiskLevel(row.risk_if_absent),
            tags=list(row.tags or []),
        )

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """Run a cosine-distance nearest-neighbor query."""
        distance = PlaybookEmbedding.embedding.cosine_distance(vector)
        with self._session_factory() as session:
            rows = (
                session.query(PlaybookEmbedding, distance.label("distance"))
                .order_by(distance)
                .limit(top_k)
                .all()
            )
        return [
            RetrievalHit(
                position=self._to_position(row),
                score=1.0 - float(dist),
                source=RetrievalSource.DENSE,
            )
            for row, dist in rows
        ]

    def list_all(self) -> list[PlaybookPosition]:
        """Return every stored position."""
        with self._session_factory() as session:
            return [self._to_position(row) for row in session.query(PlaybookEmbedding).all()]


# --- retrieval ---------------------------------------------------------------


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
            blended.append(
                RetrievalHit(position=hit.position, score=score, source=RetrievalSource.HYBRID)
            )

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


# --- citations ---------------------------------------------------------------


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


# --- ingestion ---------------------------------------------------------------


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
