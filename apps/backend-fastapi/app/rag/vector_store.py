"""Vector store adapter interface (pgvector / Qdrant)."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.dialects.postgresql import insert

from app.core.db import SessionLocal
from app.models.playbook import PlaybookEmbedding
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


class PgVectorStore:
    """pgvector-backed :class:`VectorStore` implementation.

    Reads and writes :class:`~app.models.playbook.PlaybookEmbedding` through
    the app's shared session factory (see ``app.core.db``).
    """

    def __init__(self, session_factory=SessionLocal) -> None:  # noqa: ANN001 - sessionmaker
        self._session_factory = session_factory

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
