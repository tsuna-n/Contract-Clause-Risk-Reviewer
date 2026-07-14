"""Structured logging with a per-request trace id.

Uses ``structlog`` when available; falls back to the stdlib ``logging`` module
so the app stays importable without the dependency installed.
"""

import logging
import uuid
from contextvars import ContextVar

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    """Generate and bind a fresh trace id to the current context."""
    trace_id = uuid.uuid4().hex
    _trace_id.set(trace_id)
    return trace_id


def get_trace_id() -> str | None:
    """Return the trace id bound to the current context, if any."""
    return _trace_id.get()


def configure_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    TODO: wire up structlog processors (trace_id, timestamp, JSON renderer).
    """
    logging.basicConfig(level=level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger bound to ``name``."""
    return logging.getLogger(name)
