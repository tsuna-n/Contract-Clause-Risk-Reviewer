"""Fixtures for the live-provider tests.

Everything here talks to the real vendor and the real database. Nothing in
this package runs unless it is asked for by name (``-m live_llm``), so the
fixtures may be as slow and as stateful as the thing they are checking.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.pipeline import Orchestrator
from app.ai.providers import ProviderConfigError
from app.config import get_settings
from app.parsers import ParsedDocument, parse_txt
from app.schemas import PlaybookPosition

SAMPLE = Path("data/samples/thai-nda-short.txt")


@pytest.fixture(scope="session", autouse=True)
def _require_a_configured_provider() -> None:
    """Skip the package when ``.env`` has no usable provider, instead of failing.

    A missing key is not a regression in the pipeline, and reporting it as one
    would make ``-m live_llm`` fail for the two reasons that look identical
    from the outside: the model got worse, or nobody set ``ZAI_API_KEY``.
    """
    try:
        from app.ai.providers import build_chat_backend

        build_chat_backend(get_settings())
    except ProviderConfigError as exc:  # pragma: no cover - depends on .env
        pytest.skip(f"no usable LLM provider configured: {exc}")


@pytest.fixture(scope="session")
def orchestrator() -> Orchestrator:
    """The real pipeline, wired exactly as the API wires it.

    Built through ``app.dependencies`` rather than by hand so that a change to
    the production object graph - a new agent, a different retriever - is
    covered here without anybody remembering to mirror it.
    """
    from app.dependencies import get_orchestrator

    return get_orchestrator()


@pytest.fixture(scope="session")
def known_positions() -> dict[str, PlaybookPosition]:
    """Every playbook position the judge will accept a citation to.

    Read from pgvector when it is ingested, falling back to the seed YAML -
    same source the judge itself reads, so "valid citation" means the same
    thing in the assertions as it does in the pipeline.
    """
    from app.dependencies import get_known_positions

    positions = get_known_positions()
    if not positions:  # pragma: no cover - depends on the database
        pytest.skip("no playbook positions available; run `python -m scripts.ingest_playbook`")
    return positions


@pytest.fixture(scope="session")
def sample_document() -> ParsedDocument:
    """The three-clause Thai NDA - the cheapest document with real risk in it.

    Short enough that the whole review is roughly a minute of provider time,
    and Thai on purpose: the heading rules and the prompts both have to hold
    up on the script the sample contracts are *not* written in.
    """
    if not SAMPLE.exists():  # pragma: no cover - depends on the checkout
        pytest.skip(f"sample contract missing: {SAMPLE}")
    return parse_txt(SAMPLE.read_bytes())
