"""LLM client + prompt rendering.

The one place the pipeline talks to a model API. Agents call
:meth:`LLMClient.complete` or :meth:`LLMClient.complete_structured` and never
touch a vendor SDK, so provider selection, model selection, timeouts, and usage
accounting are configured once here — and the vendor itself is an ``.env``
setting (see :mod:`app.ai.providers`).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from app.ai.providers import ChatBackend, Usage, build_chat_backend, is_transient
from app.config import get_settings
from app.logger import get_logger

# ``Usage`` lives with the backends that populate it, but is re-exported here
# because this is where the pipeline reads it from.
__all__ = ["LLMClient", "Usage", "render_prompt"]

logger = get_logger(__name__)

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

    Centralizes model selection, timeouts, retries, and usage accounting so the
    agents don't each re-implement it. The vendor SDKs retry their own transport
    errors; the retry here is a layer above that, because the failures that
    actually cost this pipeline clauses are ones the SDK considers a successful
    request — a 200 whose ``content`` is empty most of all.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout_seconds: int | None = None,
        backend: ChatBackend | None = None,
    ) -> None:
        settings = get_settings()
        self._backend = backend or build_chat_backend(
            settings, model=model, timeout_seconds=timeout_seconds
        )
        self._max_attempts = max(1, settings.llm_max_attempts)
        self._backoff_seconds = max(0.0, settings.llm_retry_backoff_seconds)
        # Retries are bounded by wall clock as well as by count, because the two
        # transient failures here cost wildly different amounts of time: an
        # empty answer comes back in seconds and is worth asking again, while a
        # timeout has already spent the ceiling and asking twice more would put
        # a single clause past six minutes. One call's timeout is the whole
        # extra budget, however it gets spent.
        self._retry_budget_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.usage = Usage()
        # One ``LLMClient`` is shared by every agent and, since the
        # orchestrator reviews several clauses at once (see
        # ``review_concurrency``), called from several threads at the same
        # time - so accumulating into ``self.usage`` needs its own lock rather
        # than relying on the caller to serialize it.
        self._usage_lock = threading.Lock()

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
        return self._call(
            lambda: self._backend.complete(
                system=system, prompt=prompt, max_tokens=max_tokens, effort=effort
            ),
            what="completion",
        )

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
        return self._call(
            lambda: self._backend.complete_structured(
                system=system,
                prompt=prompt,
                response_model=response_model,
                max_tokens=max_tokens,
            ),
            what=response_model.__name__,
        )

    def _call[T](self, attempt: Callable[[], tuple[T, Usage]], *, what: str) -> T:
        """Run ``attempt``, asking again while the failure looks survivable.

        Only the failures in :func:`~app.ai.providers.is_transient` are retried:
        a 400 or a rejected key answers the same way however often it is asked,
        and the orchestrator's per-clause isolation means the honest thing to do
        with the rest is degrade this one clause rather than stall the report.

        ``usage`` is accumulated per answer, not per attempt — a failed attempt
        raises before its token count is in hand, so a retried call is billed
        by the vendor and undercounted here. The gap is visible in the retry
        warnings below.
        """
        deadline = time.monotonic() + self._retry_budget_seconds
        number = 1
        while True:
            try:
                result, usage = attempt()
            except Exception as exc:
                out_of_attempts = number >= self._max_attempts
                out_of_time = time.monotonic() >= deadline
                if out_of_attempts or out_of_time or not is_transient(exc):
                    raise
                delay = self._backoff_seconds * 2 ** (number - 1)
                logger.warning(
                    "%s attempt %d/%d failed (%s: %s); retrying in %.1fs",
                    what,
                    number,
                    self._max_attempts,
                    type(exc).__name__,
                    exc,
                    delay,
                )
                time.sleep(delay)
                number += 1
            else:
                with self._usage_lock:
                    self.usage.add(usage)
                return result
