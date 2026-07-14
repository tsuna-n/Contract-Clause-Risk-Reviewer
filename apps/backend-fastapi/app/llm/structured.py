"""Structured output: response_model -> validated Pydantic instance."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.llm.client import LLMClient

T = TypeVar("T", bound=BaseModel)


def parse_structured(
    client: LLMClient,
    *,
    system: str,
    prompt: str,
    response_model: type[T],
    max_tokens: int = 4096,
) -> T:
    """Return a validated ``response_model`` instance from the LLM.

    Uses the Anthropic SDK's ``messages.parse`` with ``output_format`` so the
    response is constrained to the schema and validated automatically.

    TODO: call ``client._get_client().messages.parse(...)`` and return
    ``response.parsed_output``.
    """
    raise NotImplementedError
