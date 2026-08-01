"""Quota-shaped tests for the embedder decorators.

Every assertion here counts *requests*, not vectors: the free tiers this
project runs on meter calls, so "one request for eight clauses" and "no request
for a clause seen before" are the behaviours worth pinning down.
"""

from __future__ import annotations

import pytest

from app.ai.retrieval import (
    CachingEmbedder,
    DummyEmbedder,
    InMemoryEmbeddingCache,
    PgVectorStore,
    RedisEmbeddingCache,
    Retriever,
    RetryingEmbedder,
)
from app.schemas import Clause, Span


class CountingEmbedder:
    """Wraps :class:`DummyEmbedder`, recording every call it is asked to make."""

    def __init__(self, dim: int = 8) -> None:
        self.inner = DummyEmbedder(dim=dim)
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return self.inner.embed(texts)


def _clause(text: str) -> Clause:
    return Clause(id=text[:8], text=text, span=Span(start=0, end=len(text)))


def _caching(counter: CountingEmbedder) -> CachingEmbedder:
    return CachingEmbedder(counter, InMemoryEmbeddingCache(), namespace="test:model:8")


# --- caching -----------------------------------------------------------------


def test_text_already_embedded_costs_no_request() -> None:
    counter = CountingEmbedder()
    embedder = _caching(counter)

    first = embedder.embed(["termination for convenience"])
    second = embedder.embed(["termination for convenience"])

    assert first == second
    assert len(counter.calls) == 1


def test_a_batch_sends_one_request_for_only_the_misses() -> None:
    counter = CountingEmbedder()
    embedder = _caching(counter)

    embedder.embed(["a", "b"])
    embedder.embed(["a", "b", "c"])

    # Second call asks for "c" alone - not the whole batch, and not one request
    # per text.
    assert counter.calls == [["a", "b"], ["c"]]


def test_vectors_come_back_in_the_order_asked_for_duplicates_included() -> None:
    counter = CountingEmbedder()
    embedder = _caching(counter)

    vectors = embedder.embed(["b", "a", "b"])

    assert vectors[0] == vectors[2] != vectors[1]
    # A document repeats itself; the repeat must not become a second request.
    assert counter.calls == [["b", "a"]]
    assert embedder.embed([]) == []


def test_the_key_separates_models_so_switching_never_mixes_vector_spaces() -> None:
    counter = CountingEmbedder()
    cache = InMemoryEmbeddingCache()
    gemini = CachingEmbedder(counter, cache, namespace="gemini:gemini-embedding-001:768")
    other = CachingEmbedder(counter, cache, namespace="openai:text-embedding-3-small:768")

    gemini.embed(["same text"])
    other.embed(["same text"])

    assert len(counter.calls) == 2


# --- retry -------------------------------------------------------------------


class FlakyEmbedder:
    """Fails ``failures`` times with ``exc``, then answers."""

    def __init__(self, exc: Exception, failures: int) -> None:
        self.exc = exc
        self.remaining = failures
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.remaining:
            self.remaining -= 1
            raise self.exc
        return DummyEmbedder(dim=8).embed(texts)


class RateLimitError(Exception):
    """Stands in for a vendor 429 (matched by name, as `is_transient` does)."""

    status_code = 429


def test_a_429_is_retried_rather_than_costing_the_clause() -> None:
    flaky = FlakyEmbedder(RateLimitError("quota"), failures=2)
    embedder = RetryingEmbedder(flaky, max_attempts=3, backoff_seconds=0)

    assert len(embedder.embed(["clause"])[0]) == 8
    assert flaky.calls == 3


def test_a_bad_request_is_not_retried_and_attempts_are_capped() -> None:
    # The failure this whole session started from: EMBEDDING_MODEL naming a
    # model the host doesn't serve answers 400 to every attempt, so asking
    # again only delays the error that names it.
    class BadRequestError(Exception):
        status_code = 400

    flaky = FlakyEmbedder(BadRequestError("Unknown Model"), failures=99)
    with pytest.raises(BadRequestError):
        RetryingEmbedder(flaky, max_attempts=3, backoff_seconds=0).embed(["clause"])
    assert flaky.calls == 1

    flaky = FlakyEmbedder(RateLimitError("quota"), failures=99)
    with pytest.raises(RateLimitError):
        RetryingEmbedder(flaky, max_attempts=2, backoff_seconds=0).embed(["clause"])
    assert flaky.calls == 2


# --- pre-warm ----------------------------------------------------------------


def test_prewarm_turns_a_document_into_one_request() -> None:
    counter = CountingEmbedder()
    retriever = Retriever(_caching(counter), PgVectorStore())
    clauses = [_clause(f"clause number {n}") for n in range(8)]

    retriever.prewarm(clauses)
    for clause in clauses:
        retriever.embedder.embed([clause.text])  # what `retrieve` does per clause

    assert len(counter.calls) == 1
    assert len(counter.calls[0]) == 8


def test_prewarm_is_skipped_when_there_is_no_cache_to_fill() -> None:
    # Without a cache the per-clause calls can't read anything back, so a
    # pre-warm would be a request spent on nothing.
    counter = CountingEmbedder()
    retriever = Retriever(counter, PgVectorStore())

    retriever.prewarm([_clause("a clause")])
    retriever.prewarm([])

    assert counter.calls == []


# --- redis backend -----------------------------------------------------------


class BrokenRedis:
    """A Redis that is down, in the two ways the cache touches it."""

    def mget(self, keys):  # noqa: ANN001, ANN201
        raise ConnectionError("redis is down")

    def pipeline(self):  # noqa: ANN201
        raise ConnectionError("redis is down")


def test_a_broken_redis_costs_quota_not_the_review() -> None:
    counter = CountingEmbedder()
    embedder = CachingEmbedder(counter, RedisEmbeddingCache(BrokenRedis(), 60), namespace="ns")

    assert len(embedder.embed(["clause"])[0]) == 8
    # Every call is a miss while Redis is down - but the review still runs.
    assert len(embedder.embed(["clause"])[0]) == 8
    assert len(counter.calls) == 2


def test_a_corrupt_cache_entry_is_re_embedded_rather_than_raising() -> None:
    class GarbageRedis:
        def mget(self, keys):  # noqa: ANN001, ANN201
            return ["not json" for _ in keys]

        def pipeline(self):  # noqa: ANN201
            raise AssertionError("unreachable in this test")

    counter = CountingEmbedder()
    embedder = CachingEmbedder(counter, RedisEmbeddingCache(GarbageRedis(), 60), namespace="ns")
    embedder.cache.set_many = lambda vectors: None  # writes aren't what's under test

    assert len(embedder.embed(["clause"])[0]) == 8
