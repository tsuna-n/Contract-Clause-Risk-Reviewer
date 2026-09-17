"""Exercise OpenRouter embedding requests through the real OpenAI SDK offline."""

import json

import httpx
import openai
import pytest

from app.ai.retrieval import OpenAICompatibleEmbedder, RetryingEmbedder, build_embedder
from app.config import get_settings


def _embedder(handler):
    settings = get_settings().model_copy(
        update={
            "llm_provider": "zai",
            "llm_base_url": "https://api.z.ai/api/paas/v4",
            "embedding_provider": "openrouter",
            "embedding_model": None,
            "embedding_base_url": None,
            "embedding_api_key": None,
            "openrouter_api_key": "test-key",
            "embedding_dim": 768,
            "enable_embedding_cache": False,
        }
    )
    wrapper = build_embedder(settings)
    assert isinstance(wrapper, RetryingEmbedder)
    embedder = wrapper.inner
    assert isinstance(embedder, OpenAICompatibleEmbedder)
    embedder._client = openai.OpenAI(
        api_key=embedder._api_key,
        base_url=embedder._base_url,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return embedder


def _response():
    return httpx.Response(
        200,
        json={
            "object": "list",
            "model": "google/gemini-embedding-001",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.25] * 768}],
            "usage": {"prompt_tokens": 2, "total_tokens": 2},
        },
    )


def test_openrouter_uses_its_own_host_key_dimensions_and_document_task():
    def handler(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "google/gemini-embedding-001",
            "input": ["contract clause"],
            "dimensions": 768,
            "encoding_format": "float",
            "input_type": "search_document",
        }
        return _response()

    assert _embedder(handler).embed(["contract clause"]) == [[0.25] * 768]


@pytest.mark.parametrize("status", [401, 429, 503])
def test_auth_and_transient_errors_preserve_dimensions_for_retry(status):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(status, json={"error": {"message": "request failed"}})

    embedder = _embedder(handler)
    with pytest.raises(openai.APIStatusError):
        embedder.embed(["contract clause"])
    assert len(calls) == 1
    assert embedder._supports_dimensions is True


def test_only_dimensions_rejection_retries_without_dimensions():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(400, json={"error": {"message": "dimensions unsupported"}})
        return _response()

    embedder = _embedder(handler)
    assert embedder.embed(["contract clause"]) == [[0.25] * 768]
    assert "dimensions" in calls[0]
    assert "dimensions" not in calls[1]
