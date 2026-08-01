"""Grounded RAG: embed -> store -> retrieve -> cite.

One module for the whole retrieval side, in the order data flows through it:
playbook YAML is embedded and upserted into pgvector (``ingest``), a clause is
embedded and matched against it (:class:`Retriever`), and the winning positions
become citations (:func:`make_citation`).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Protocol

import yaml
from sqlalchemy.dialects.postgresql import insert

from app.ai.providers import (
    GEMINI,
    ProviderConfigError,
    is_transient,
    resolve_api_key,
    resolve_base_url,
    resolve_embedding_model,
    resolve_embedding_provider,
)
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.logger import get_logger
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

logger = get_logger(__name__)

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
        api_key: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or resolve_embedding_model(GEMINI, settings.embedding_model)
        self.dim = dim or settings.embedding_dim
        self._api_key = api_key or resolve_api_key(
            settings, GEMINI, override=settings.embedding_api_key
        )
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


class OpenAICompatibleEmbedder:
    """Embedder for any OpenAI-shaped embeddings API, Z.AI's included.

    ``dimensions`` is optional in that API and not every host implements it, so
    a rejection is treated as "this model has one fixed width" and retried
    without it. The width still has to match ``EMBEDDING_DIM``: the playbook
    repository silently stores a zero vector for a mismatched length, which
    would make positions unretrievable with nothing in the logs to explain it.
    """

    def __init__(
        self,
        model: str | None = None,
        dim: int | None = None,
        timeout_seconds: int | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        resolved_provider = provider or resolve_embedding_provider(settings)
        self.model = model or resolve_embedding_model(resolved_provider, settings.embedding_model)
        self.dim = dim or settings.embedding_dim
        self._api_key = api_key or resolve_api_key(
            settings, resolved_provider, override=settings.embedding_api_key
        )
        self._base_url = base_url or resolve_base_url(
            resolved_provider, settings.embedding_base_url or settings.llm_base_url
        )
        self._timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self._client = None  # lazily constructed openai.OpenAI
        self._supports_dimensions = True

    def _get_client(self):
        """Lazily construct the underlying ``openai.OpenAI`` client."""
        if self._client is None:
            import openai

            # The OpenAI SDK takes seconds, unlike Gemini's milliseconds.
            self._client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            )
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        if not texts:
            return []

        if self._supports_dimensions:
            try:
                response = self._get_client().embeddings.create(
                    model=self.model, input=texts, dimensions=self.dim
                )
                return self._vectors(response)
            except Exception:  # noqa: BLE001 - host may not implement `dimensions`
                self._supports_dimensions = False

        response = self._get_client().embeddings.create(model=self.model, input=texts)
        return self._vectors(response)

    def _vectors(self, response) -> list[list[float]]:
        vectors = [list(item.embedding) for item in response.data]
        if vectors and len(vectors[0]) != self.dim:
            raise ProviderConfigError(
                f"{self.model} returned {len(vectors[0])}-dim vectors but EMBEDDING_DIM is "
                f"{self.dim}; set EMBEDDING_DIM to match and re-run the Alembic migration "
                "plus `python -m scripts.ingest_playbook`"
            )
        return vectors


class EmbeddingCache(Protocol):
    """Somewhere to keep vectors between calls."""

    def get_many(self, keys: list[str]) -> dict[str, list[float]]:
        """Return the vectors present for ``keys``; missing keys are absent."""
        ...

    def set_many(self, vectors: dict[str, list[float]]) -> None:
        """Store each key's vector."""
        ...


class InMemoryEmbeddingCache:
    """Process-local cache. The default, and all a script or a test needs."""

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def get_many(self, keys: list[str]) -> dict[str, list[float]]:
        """Return the vectors present for ``keys``."""
        return {key: self._vectors[key] for key in keys if key in self._vectors}

    def set_many(self, vectors: dict[str, list[float]]) -> None:
        """Store each key's vector for the life of the process."""
        self._vectors.update(vectors)


class RedisEmbeddingCache:
    """Cache shared across workers and across restarts.

    Every operation is best-effort. A cache is an optimization, and Redis being
    down has to cost a review some quota rather than cost it a report — so a
    failed read is a miss and a failed write is dropped, both with a warning
    and nothing else. Redis is already in the stack for contract and report
    storage (see ``app/dependencies.py``), so this adds no new dependency.
    """

    def __init__(self, client, ttl_seconds: int) -> None:  # noqa: ANN001 - redis.Redis
        self._client = client
        self._ttl_seconds = ttl_seconds

    def get_many(self, keys: list[str]) -> dict[str, list[float]]:
        """Return the vectors Redis holds for ``keys``, or none of them."""
        if not keys:
            return {}
        try:
            raw = self._client.mget(keys)
        except Exception:  # noqa: BLE001 - a cache miss is the safe reading
            logger.warning("embedding cache read failed; treating as a miss", exc_info=True)
            return {}
        found: dict[str, list[float]] = {}
        for key, value in zip(keys, raw, strict=True):
            if not value:
                continue
            try:
                found[key] = json.loads(value)
            except (TypeError, ValueError):
                # A corrupt entry re-embeds and overwrites itself on the way
                # back through ``set_many``.
                logger.warning("embedding cache entry %s is not valid JSON; ignoring", key)
        return found

    def set_many(self, vectors: dict[str, list[float]]) -> None:
        """Store each key's vector under the configured TTL."""
        if not vectors:
            return
        try:
            pipe = self._client.pipeline()
            for key, vector in vectors.items():
                pipe.set(key, json.dumps(vector), ex=self._ttl_seconds)
            pipe.execute()
        except Exception:  # noqa: BLE001 - losing a write only costs quota later
            logger.warning("embedding cache write failed; vectors not stored", exc_info=True)


class RetryingEmbedder:
    """Embedder decorator that asks again while the failure looks survivable.

    The chat side has had this since the beginning (``LLMClient._call``); the
    embedding side had nothing, so a single 429 — which on a free tier means
    "next minute", not "no" — ended that clause as ``unknown`` with the
    pipeline's per-clause isolation swallowing the reason. Same predicate and
    same settings as the chat retries, so the two behave alike.
    """

    def __init__(self, inner: Embedder, *, max_attempts: int, backoff_seconds: float) -> None:
        self.inner = inner
        self._max_attempts = max(1, max_attempts)
        self._backoff_seconds = max(0.0, backoff_seconds)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts``, retrying transient failures with a growing delay."""
        number = 1
        while True:
            try:
                return self.inner.embed(texts)
            except Exception as exc:
                if number >= self._max_attempts or not is_transient(exc):
                    raise
                delay = self._backoff_seconds * 2 ** (number - 1)
                logger.warning(
                    "embedding attempt %d/%d failed (%s: %s); retrying in %.1fs",
                    number,
                    self._max_attempts,
                    type(exc).__name__,
                    exc,
                    delay,
                )
                time.sleep(delay)
                number += 1


class CachingEmbedder:
    """Embedder decorator that reuses known vectors and batches the rest.

    Two savings, both aimed at request count rather than tokens, because that
    is what the free tiers meter:

    * text already embedded costs nothing — a re-review of the same contract,
      or a second eval pass over the same fixtures, sends no request at all;
    * a call for many texts sends *one* request for whichever of them are
      missing, which is what makes :meth:`Retriever.prewarm` worth doing —
      the whole document embeds in one call and the per-clause retrievals that
      follow are cache reads.

    The key carries the provider, model and width alongside the text, so
    switching any of them starts from an empty cache instead of silently
    mixing vector spaces.
    """

    def __init__(self, inner: Embedder, cache: EmbeddingCache, *, namespace: str) -> None:
        self.inner = inner
        self.cache = cache
        self._namespace = namespace

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"emb:{self._namespace}:{digest}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, embedding only what isn't cached."""
        if not texts:
            return []

        keys = [self._key(text) for text in texts]
        known = self.cache.get_many(list(dict.fromkeys(keys)))

        # A document repeats itself - identical clauses, a heading quoted twice
        # - so the misses are deduplicated before the request, not after.
        missing: dict[str, str] = {}
        for key, text in zip(keys, texts, strict=True):
            if key not in known:
                missing.setdefault(key, text)

        if missing:
            vectors = self.inner.embed(list(missing.values()))
            fresh = dict(zip(missing.keys(), vectors, strict=True))
            self.cache.set_many(fresh)
            known.update(fresh)

        return [known[key] for key in keys]

    def prewarm(self, texts: list[str]) -> None:
        """Fill the cache for ``texts`` in a single request."""
        self.embed(texts)


def build_embedder(
    settings: Settings | None = None, cache: EmbeddingCache | None = None
) -> Embedder:
    """Construct the embedder described by settings.

    Separate from the chat provider on purpose: neither Anthropic nor Z.AI
    serves an embedding model this app can reach, so a Claude- or GLM-reviewed
    deployment still retrieves through Gemini (or any OpenAI-compatible host)
    without the two settings fighting each other. It has to stay whichever
    provider filled ``playbook_embeddings``, too — vectors from two different
    models share a table but not a space, and cosine distance between them is
    noise that still returns five confident-looking hits.

    The provider client is wrapped in retry and (unless
    ``ENABLE_EMBEDDING_CACHE=false``) caching. ``cache`` defaults to a
    process-local dict, which is right for scripts and tests; the app passes a
    Redis-backed one so the vectors outlive a restart.
    """
    settings = settings or get_settings()
    provider = resolve_embedding_provider(settings)
    base = GeminiEmbedder() if provider == GEMINI else OpenAICompatibleEmbedder(provider=provider)

    embedder: Embedder = RetryingEmbedder(
        base,
        max_attempts=settings.llm_max_attempts,
        backoff_seconds=settings.llm_retry_backoff_seconds,
    )
    if not settings.enable_embedding_cache:
        return embedder
    return CachingEmbedder(
        embedder,
        cache if cache is not None else InMemoryEmbeddingCache(),
        namespace=f"{provider}:{base.model}:{base.dim}",
    )


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

    def prewarm(self, clauses: list[Clause]) -> None:
        """Embed a whole document in one request, ahead of the per-clause work.

        :meth:`retrieve` embeds one clause at a time because that is the shape
        of the pipeline, and free-tier quotas count requests — so an eight
        clause contract spent eight of them on work one request could do. With
        a :class:`CachingEmbedder` underneath, those eight calls now read back
        what this stored. Without one there is nothing to read back from, so
        this would be a wasted request and is skipped instead.
        """
        if not isinstance(self.embedder, CachingEmbedder) or not clauses:
            return
        self.embedder.prewarm([clause.text for clause in clauses])

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
