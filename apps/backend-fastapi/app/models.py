"""SQLAlchemy ORM models — every persistent table in the system.

Importing this module is enough to populate ``Base.metadata``, which is what
Alembic autogenerate diffs against the live database.

Only long-lived data lives here. Uploaded contracts and generated reports are
session-scoped and kept in Redis instead (see ``app/repositories``).
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.config import get_settings
from app.database import Base

__all__ = ["AuditOverride", "Base", "PlaybookEmbedding", "User"]


class User(Base):
    """A signed-in user, keyed by their Google identity."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Google "sub" claim
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditOverride(Base):
    """A single human override of an automated assessment.

    Unlike contracts and reports (session-scoped, Redis, TTL'd), this log is
    retained indefinitely for accountability. Read/write goes through
    :class:`~app.repositories.audit.AuditRepository`.
    """

    __tablename__ = "audit_overrides"

    id = Column(String, primary_key=True)
    report_id = Column(String, nullable=False, index=True)
    clause_id = Column(String, nullable=False)
    old_risk = Column(String, nullable=False)
    new_risk = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlaybookEmbedding(Base):
    """One playbook position, stored alongside its embedding vector.

    Written by ``scripts/ingest_playbook.py`` and queried by
    :class:`~app.ai.retrieval.PgVectorStore`.
    """

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
