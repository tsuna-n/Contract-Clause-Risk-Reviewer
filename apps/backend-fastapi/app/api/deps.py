"""Dependency-injection providers: DB session, vector store, LLM client."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.llm.client import LLMClient
    from app.rag.vector_store import VectorStore

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Yield a scoped SQLAlchemy session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_vector_store() -> "VectorStore":
    """Return the configured vector store adapter.

    TODO: construct the pgvector/Qdrant adapter from settings.
    """
    raise NotImplementedError


def get_llm_client() -> "LLMClient":
    """Return the shared LLM client wrapper.

    TODO: construct :class:`app.llm.client.LLMClient` from settings.
    """
    raise NotImplementedError
