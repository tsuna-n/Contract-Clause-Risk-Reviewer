"""Structured output: response_model -> validated Pydantic instance."""

from __future__ import annotations

from pydantic import BaseModel

from app.llm.client import LLMClient


def parse_structured[T: BaseModel](
    client: LLMClient,
    *,
    system: str,
    prompt: str,
    response_model: type[T],
    max_tokens: int = 4096,
) -> T:
    """Return a validated ``response_model`` instance from the LLM.

    Uses the Google GenAI SDK's ``response_schema``/``response_mime_type``
    controls so the response is constrained to the schema and validated
    automatically, then re-validates through pydantic for good measure.
    """
    from google.genai import types

    response = client._get_client().models.generate_content(
        model=client.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            response_schema=response_model,
        ),
    )
    client._record_usage(response)
    parsed = response.parsed
    if isinstance(parsed, response_model):
        return parsed
    return response_model.model_validate_json(response.text)
