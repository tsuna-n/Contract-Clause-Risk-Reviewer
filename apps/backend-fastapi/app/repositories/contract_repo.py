"""Session-scoped storage for uploaded/parsed contracts (in-memory / redis)."""

from __future__ import annotations

from app.parsers.models import ParsedDocument


class ContractRepository:
    """Stores parsed contracts for the lifetime of a session only.

    Uploaded contracts must not be retained beyond the session TTL (see
    ``core.retention``). Default implementation is in-memory; a redis-backed
    variant can share the same interface.
    """

    def __init__(self) -> None:
        self._store: dict[str, ParsedDocument] = {}

    def save(self, contract_id: str, document: ParsedDocument) -> None:
        """Persist ``document`` under ``contract_id`` for this session."""
        self._store[contract_id] = document

    def get(self, contract_id: str) -> ParsedDocument | None:
        """Return the parsed contract, or ``None`` if absent/expired."""
        return self._store.get(contract_id)

    def delete(self, contract_id: str) -> None:
        """Remove a contract from the session store."""
        self._store.pop(contract_id, None)
