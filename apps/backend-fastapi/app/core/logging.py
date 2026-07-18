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

    Wires structlog processors (trace id, timestamp, JSON renderer) into the
    stdlib logging formatter, so plain ``logging.getLogger()`` loggers (see
    :func:`get_logger`) emit structured JSON without every call site needing
    to know about structlog.
    """
    try:
        import structlog
    except ImportError:
        logging.basicConfig(level=level)
        return

    def _add_trace_id(logger, method_name, event_dict):  # noqa: ANN001 - structlog processor
        trace_id = get_trace_id()
        if trace_id:
            event_dict["trace_id"] = trace_id
        return event_dict

    shared_processors = [
        _add_trace_id,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger bound to ``name``."""
    return logging.getLogger(name)
