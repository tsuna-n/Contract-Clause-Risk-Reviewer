"""Session-scoped storage for uploaded/parsed contracts (in-memory / redis)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol

from app.parsers.models import ParsedDocument, TextSpan


class ContractRepository(Protocol):
    """Storage interface for parsed contracts, scoped to a single session.

    Uploaded contracts must not be retained beyond the session TTL (enforced
    by ``ReviewService``). :class:`InMemoryContractRepository` and
    :class:`RedisContractRepository` both satisfy this interface.
    """

    def save(self, contract_id: str, document: ParsedDocument) -> None:
        """Persist ``document`` under ``contract_id`` for this session."""
        ...

    def get(self, contract_id: str) -> ParsedDocument | None:
        """Return the parsed contract, or ``None`` if absent/expired."""
        ...

    def delete(self, contract_id: str) -> None:
        """Remove a contract from the session store."""
        ...


class InMemoryContractRepository:
    """Process-local dict-backed store.

    Fine for a single worker process; does not share state across
    processes/replicas — see :class:`RedisContractRepository` for that.
    """

    def __init__(self) -> None:
        self._store: dict[str, ParsedDocument] = {}

    def save(self, contract_id: str, document: ParsedDocument) -> None:
        self._store[contract_id] = document

    def get(self, contract_id: str) -> ParsedDocument | None:
        return self._store.get(contract_id)

    def delete(self, contract_id: str) -> None:
        self._store.pop(contract_id, None)


def _serialize_document(document: ParsedDocument) -> str:
    return json.dumps(
        {
            "text": document.text,
            "spans": [asdict(span) for span in document.spans],
            "page_map": {str(page): list(bounds) for page, bounds in document.page_map.items()},
        }
    )


def _deserialize_document(data: str) -> ParsedDocument:
    obj = json.loads(data)
    return ParsedDocument(
        text=obj["text"],
        spans=[TextSpan(**span) for span in obj["spans"]],
        page_map={int(page): tuple(bounds) for page, bounds in obj["page_map"].items()},
    )


class RedisContractRepository:
    """Redis-backed :class:`ContractRepository`.

    ``ReviewService`` already deletes a contract explicitly right after
    producing its report; the TTL set here is only a safety net so a raw
    contract can never outlive the session retention window even if that
    explicit delete is skipped (e.g. a crash mid-request). Sharing state via
    Redis (instead of a process-local dict) is what lets the API scale
    across multiple worker processes/replicas.
    """

    def __init__(self, client: Any, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(contract_id: str) -> str:
        return f"contract:{contract_id}"

    def save(self, contract_id: str, document: ParsedDocument) -> None:
        self._client.set(
            self._key(contract_id), _serialize_document(document), ex=self._ttl_seconds
        )

    def get(self, contract_id: str) -> ParsedDocument | None:
        data = self._client.get(self._key(contract_id))
        return _deserialize_document(data) if data is not None else None

    def delete(self, contract_id: str) -> None:
        self._client.delete(self._key(contract_id))
