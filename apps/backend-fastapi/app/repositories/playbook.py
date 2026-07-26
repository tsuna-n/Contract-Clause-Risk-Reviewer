"""Playbook repository for CRUD operations on playbook positions stored in PostgreSQL."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PlaybookEmbedding
from app.schemas import PlaybookPositionCreate, PlaybookPositionUpdate


class PlaybookRepository:
    """PostgreSQL-backed store for playbook positions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self, clause_type: str | None = None) -> Sequence[PlaybookEmbedding]:
        """Return all playbook positions, optionally filtered by clause type."""
        query = self.db.query(PlaybookEmbedding)
        if clause_type:
            query = query.filter(PlaybookEmbedding.clause_type == clause_type)
        return query.order_by(PlaybookEmbedding.clause_type, PlaybookEmbedding.title).all()

    def get_by_id(self, position_id: str) -> PlaybookEmbedding | None:
        """Return a single playbook position by ID."""
        return self.db.get(PlaybookEmbedding, position_id)

    def create(
        self, payload: PlaybookPositionCreate, embedding: list[float] | None = None
    ) -> PlaybookEmbedding:
        """Create and persist a new playbook position."""
        position_id = payload.id or f"pb_{uuid.uuid4().hex[:8]}"
        dim = get_settings().embedding_dim
        vec = embedding if embedding and len(embedding) == dim else [0.0] * dim

        row = PlaybookEmbedding(
            id=position_id,
            clause_type=payload.clause_type.value,
            title=payload.title,
            preferred_language=payload.preferred_language,
            fallback_language=payload.fallback_language,
            risk_if_absent=payload.risk_if_absent.value,
            tags=payload.tags,
            embedding=vec,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(
        self,
        position_id: str,
        payload: PlaybookPositionUpdate,
        embedding: list[float] | None = None,
    ) -> PlaybookEmbedding | None:
        """Update an existing playbook position."""
        row = self.get_by_id(position_id)
        if row is None:
            return None

        if payload.clause_type is not None:
            row.clause_type = payload.clause_type.value
        if payload.title is not None:
            row.title = payload.title
        if payload.preferred_language is not None:
            row.preferred_language = payload.preferred_language
        if payload.fallback_language is not None:
            row.fallback_language = payload.fallback_language
        if payload.risk_if_absent is not None:
            row.risk_if_absent = payload.risk_if_absent.value
        if payload.tags is not None:
            row.tags = payload.tags

        if embedding is not None and len(embedding) == get_settings().embedding_dim:
            row.embedding = embedding

        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, position_id: str) -> bool:
        """Delete a playbook position by ID."""
        row = self.get_by_id(position_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
