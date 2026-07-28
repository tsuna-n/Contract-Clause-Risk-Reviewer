"""LLM client + prompt rendering.

The one place the pipeline talks to a model API. Agents call
:meth:`LLMClient.complete` or :meth:`LLMClient.complete_structured` and never
touch a vendor SDK, so provider selection, model selection, timeouts, and usage
accounting are configured once here — and the vendor itself is an ``.env``
setting (see :mod:`app.ai.providers`).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from app.ai.providers import ChatBackend, Usage, build_chat_backend
from app.config import get_settings

# ``Usage`` lives with the backends that populate it, but is re-exported here
# because this is where the pipeline reads it from.
__all__ = ["LLMClient", "Usage", "render_prompt"]

# --- prompt templates --------------------------------------------------------

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "prompts"),
    autoescape=select_autoescape(disabled_extensions=("jinja",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **context: object) -> str:
    """Render ``template_name`` (e.g. ``classifier.v1.jinja``) with ``context``."""
    return _env.get_template(template_name).render(**context)


# --- client ------------------------------------------------------------------


class LLMClient:
    """Provider-agnostic wrapper over whichever vendor ``.env`` selects.

    Centralizes model selection, timeouts, and usage accounting so the agents
    don't each re-implement it. The vendor SDKs retry transient errors
    themselves; this wrapper adds cost tracking and a single place to set
    defaults.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout_seconds: int | None = None,
        backend: ChatBackend | None = None,
    ) -> None:
        self._backend = backend or build_chat_backend(
            get_settings(), model=model, timeout_seconds=timeout_seconds
        )
        self.usage = Usage()

    @property
    def model(self) -> str:
        """The model actually in use, after provider defaults are applied."""
        return self._backend.model

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 4096,
        effort: str = "high",
    ) -> str:
        """Run a single completion and return the text."""
        text, usage = self._backend.complete(
            system=system, prompt=prompt, max_tokens=max_tokens, effort=effort
        )
        self.usage.add(usage)
        return text

    def complete_structured[T: BaseModel](
        self,
        *,
        system: str,
        prompt: str,
        response_model: type[T],
        max_tokens: int = 4096,
    ) -> T:
        """Return a validated ``response_model`` instance from the LLM.

        Each backend uses its provider's own schema-constrained output mode and
        re-validates through pydantic, so a clause the model answers badly
        fails here rather than reaching the guardrails half-formed.
        """
        parsed, usage = self._backend.complete_structured(
            system=system,
            prompt=prompt,
            response_model=response_model,
            max_tokens=max_tokens,
        )
        self.usage.add(usage)
        return parsed
