"""Playbook retrieval debug endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.playbook import RetrievalHit

router = APIRouter(prefix="/playbook", tags=["playbook"])


@router.get("/search", response_model=list[RetrievalHit])
async def search_playbook(q: str, top_k: int = 5) -> list[RetrievalHit]:
    """Debug endpoint: return playbook positions matching a free-text query.

    TODO: embed ``q`` and query the retriever/vector store (via DI).
    """
    raise NotImplementedError
