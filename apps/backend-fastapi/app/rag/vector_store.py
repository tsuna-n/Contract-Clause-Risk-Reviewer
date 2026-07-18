"""Vector store adapter interface (pgvector / Qdrant)."""

from __future__ import annotations

from typing import Protocol

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Session

from app.api.deps import Base, SessionLocal
from app.core.config import get_settings
from app.schemas.playbook import PlaybookPosition, RetrievalHit
from app.schemas.taxonomy import ClauseType, RiskLevel


class VectorStore(Protocol):
    """Storage + similarity search over playbook chunks."""

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """Insert or update a position's vector."""
        ...

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """Return the ``top_k`` nearest positions to ``vector``."""
        ...


class PlaybookEmbedding(Base):
    """ORM model backing :class:`PgVectorStore` (table: ``playbook_embeddings``)."""

    __tablename__ = "playbook_embeddings"

    id = Column(String, primary_key=True)
    clause_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    preferred_language = Column(String, nullable=False)
    fallback_language = Column(String, nullable=False)
    risk_if_absent = Column(String, nullable=False)
    tags = Column(JSONB, nullable=False, default=list)
    embedding = Column(Vector(get_settings().embedding_dim), nullable=False)


class PgVectorStore:
    """pgvector-backed :class:`VectorStore` implementation.

    Shares the app's engine/session factory (see ``app.api.deps``) so its
    table participates in the normal startup ``create_all``.
    """

    def __init__(self, dsn: str, session_factory: type[Session] | None = None) -> None:
        self.dsn = dsn
        self._session_factory = session_factory or SessionLocal

    def upsert(self, position: PlaybookPosition, vector: list[float]) -> None:
        """Upsert ``position`` and its embedding into ``playbook_embeddings``."""
        stmt = insert(PlaybookEmbedding).values(
            id=position.id,
            clause_type=position.clause_type.value,
            title=position.title,
            preferred_language=position.preferred_language,
            fallback_language=position.fallback_language,
            risk_if_absent=position.risk_if_absent.value,
            tags=position.tags,
            embedding=vector,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PlaybookEmbedding.id],
            set_={
                "clause_type": stmt.excluded.clause_type,
                "title": stmt.excluded.title,
                "preferred_language": stmt.excluded.preferred_language,
                "fallback_language": stmt.excluded.fallback_language,
                "risk_if_absent": stmt.excluded.risk_if_absent,
                "tags": stmt.excluded.tags,
                "embedding": stmt.excluded.embedding,
            },
        )
        with self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def query(self, vector: list[float], top_k: int = 5) -> list[RetrievalHit]:
        """Run a cosine-distance nearest-neighbor query."""
        distance = PlaybookEmbedding.embedding.cosine_distance(vector)
        with self._session_factory() as session:
            rows = (
                session.query(PlaybookEmbedding, distance.label("distance"))
                .order_by(distance)
                .limit(top_k)
                .all()
            )
        hits: list[RetrievalHit] = []
        for row, dist in rows:
            position = PlaybookPosition(
                id=row.id,
                clause_type=ClauseType(row.clause_type),
                title=row.title,
                preferred_language=row.preferred_language,
                fallback_language=row.fallback_language,
                risk_if_absent=RiskLevel(row.risk_if_absent),
                tags=list(row.tags or []),
            )
            hits.append(RetrievalHit(position=position, score=1.0 - float(dist), source="dense"))
        return hits
