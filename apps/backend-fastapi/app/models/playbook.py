"""The ``playbook_embeddings`` table — playbook positions + their vectors.

Written by ``scripts/ingest_playbook.py`` and queried by
:class:`~app.rag.vector_store.PgVectorStore`.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB

from app.core.config import get_settings
from app.core.db import Base


class PlaybookEmbedding(Base):
    """One playbook position, stored alongside its embedding vector."""

    __tablename__ = "playbook_embeddings"

    id = Column(String, primary_key=True)
    clause_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    preferred_language = Column(String, nullable=False)
    fallback_language = Column(String, nullable=False)
    risk_if_absent = Column(String, nullable=False)
    tags = Column(JSONB, nullable=False, default=list)
    # Width must match EMBEDDING_DIM and the Alembic migration; changing it
    # needs a new migration plus a re-ingest of the playbook.
    embedding = Column(Vector(get_settings().embedding_dim), nullable=False)
