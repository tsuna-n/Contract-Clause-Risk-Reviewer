"""Playbook retrieval debug endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_retriever
from app.rag.retriever import Retriever
from app.schemas.clause import Clause, Span
from app.schemas.playbook import RetrievalHit

router = APIRouter(prefix="/playbook", tags=["playbook"])


@router.get("/search", response_model=list[RetrievalHit])
async def search_playbook(
    q: str,
    top_k: int = 5,
    retriever: Retriever = Depends(get_retriever),
) -> list[RetrievalHit]:
    """Debug endpoint: return playbook positions matching a free-text query."""
    query_clause = Clause(id="query", text=q, span=Span(start=0, end=len(q)))
    return retriever.retrieve(query_clause, top_k=top_k)
