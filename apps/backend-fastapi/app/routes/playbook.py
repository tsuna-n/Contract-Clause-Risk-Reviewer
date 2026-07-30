"""Playbook retrieval + CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.ai.retrieval import Retriever
from app.dependencies import get_current_user, get_playbook_service, get_retriever
from app.schemas import (
    Clause,
    PlaybookPosition,
    PlaybookPositionCreate,
    PlaybookPositionUpdate,
    RetrievalHit,
    Span,
)
from app.services.playbook import PlaybookService

# Auth is declared on the router, not per endpoint, because every one of these
# needs it and the per-endpoint version is the kind of thing a sixth endpoint
# forgets - which is exactly what happened here: all six were public until
# 2026-07-30. The playbook is what the judge grounds citations against, so
# write access to it is write access to every verdict the system reaches.
#
# Not scoped per user, unlike ``/contracts``: a playbook is the company's, so
# any signed-in reviewer reads and edits the same one. That makes this
# authentication without authorization - fine while every account belongs to
# the same team, and the place to add roles when that stops being true.
router = APIRouter(
    prefix="/playbook",
    tags=["playbook"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/search", response_model=list[RetrievalHit])
def search_playbook(
    q: str,
    top_k: int = 5,
    retriever: Retriever = Depends(get_retriever),
) -> list[RetrievalHit]:
    """Debug endpoint: return playbook positions matching a free-text query.

    Declared before ``/{position_id}`` on purpose — without that ordering a
    request to ``/playbook/search`` would match the parameter route with
    ``position_id == "search"`` and 404 instead of searching.
    """
    query_clause = Clause(id="query", text=q, span=Span(start=0, end=len(q)))
    return retriever.retrieve(query_clause, top_k=top_k)


@router.get("", response_model=list[PlaybookPosition])
def list_playbook(
    clause_type: str | None = None,
    service: PlaybookService = Depends(get_playbook_service),
) -> list[PlaybookPosition]:
    """List playbook positions, optionally filtered by clause type."""
    return service.list_positions(clause_type=clause_type)


@router.post(
    "",
    response_model=PlaybookPosition,
    status_code=status.HTTP_201_CREATED,
)
def create_playbook(
    payload: PlaybookPositionCreate,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookPosition:
    """Create a new playbook position."""
    return service.create_position(payload)


@router.get("/{position_id}", response_model=PlaybookPosition)
def get_playbook(
    position_id: str,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookPosition:
    """Return a single playbook position by ID."""
    return service.get_position(position_id)


@router.put("/{position_id}", response_model=PlaybookPosition)
def update_playbook(
    position_id: str,
    payload: PlaybookPositionUpdate,
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookPosition:
    """Update an existing playbook position."""
    return service.update_position(position_id, payload)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playbook(
    position_id: str,
    service: PlaybookService = Depends(get_playbook_service),
) -> None:
    """Delete a playbook position by ID."""
    service.delete_position(position_id)
