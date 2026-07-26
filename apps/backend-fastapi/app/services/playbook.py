"""Playbook service for managing playbook rules and positions."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.ai.retrieval import Embedder
from app.repositories.playbook import PlaybookRepository
from app.schemas import PlaybookPosition, PlaybookPositionCreate, PlaybookPositionUpdate


class PlaybookService:
    """Business logic for playbook CRUD operations."""

    def __init__(self, repo: PlaybookRepository, embedder: Embedder | None = None) -> None:
        self.repo = repo
        self.embedder = embedder

    def _to_schema(self, row) -> PlaybookPosition:
        return PlaybookPosition(
            id=row.id,
            clause_type=row.clause_type,
            title=row.title,
            preferred_language=row.preferred_language,
            fallback_language=row.fallback_language,
            risk_if_absent=row.risk_if_absent,
            tags=row.tags or [],
        )

    def _gen_embedding(self, title: str, preferred: str) -> list[float] | None:
        if self.embedder is None:
            return None
        try:
            vecs = self.embedder.embed([f"{title}\n{preferred}"])
            return vecs[0] if vecs else None
        except Exception:
            return None

    def list_positions(self, clause_type: str | None = None) -> list[PlaybookPosition]:
        """List all positions, optionally filtered by category."""
        rows = self.repo.list_all(clause_type=clause_type)
        return [self._to_schema(r) for r in rows]

    def get_position(self, position_id: str) -> PlaybookPosition:
        """Get position by ID or raise 404."""
        row = self.repo.get_by_id(position_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playbook position '{position_id}' not found",
            )
        return self._to_schema(row)

    def create_position(self, payload: PlaybookPositionCreate) -> PlaybookPosition:
        """Create new position with computed embedding."""
        vec = self._gen_embedding(payload.title, payload.preferred_language)
        row = self.repo.create(payload, embedding=vec)
        return self._to_schema(row)

    def update_position(
        self, position_id: str, payload: PlaybookPositionUpdate
    ) -> PlaybookPosition:
        """Update existing position."""
        existing = self.repo.get_by_id(position_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playbook position '{position_id}' not found",
            )

        title = payload.title or existing.title
        preferred = payload.preferred_language or existing.preferred_language
        vec = self._gen_embedding(title, preferred)

        updated = self.repo.update(position_id, payload, embedding=vec)
        return self._to_schema(updated)

    def delete_position(self, position_id: str) -> None:
        """Delete position by ID or raise 404."""
        success = self.repo.delete(position_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playbook position '{position_id}' not found",
            )
