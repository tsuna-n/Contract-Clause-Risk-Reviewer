"""Domain errors and their HTTP mapping."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level errors.

    ``status_code`` is used by the API layer to map the error onto an HTTP
    response (see ``register_exception_handlers``).
    """

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentParseError(DomainError):
    """Raised when an uploaded contract cannot be parsed."""

    status_code = 422
    code = "document_parse_error"


class GroundingError(DomainError):
    """Raised when a generated excerpt/citation is not grounded in the source."""

    status_code = 422
    code = "grounding_error"


class RetrievalError(DomainError):
    """Raised when the playbook retriever fails."""

    status_code = 502
    code = "retrieval_error"


class NotFoundError(DomainError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    code = "not_found"


def register_exception_handlers(app) -> None:  # noqa: ANN001 - FastAPI app
    """Register handlers mapping :class:`DomainError` to JSON responses.

    TODO: implement with ``app.exception_handler(DomainError)``.
    """
    raise NotImplementedError
