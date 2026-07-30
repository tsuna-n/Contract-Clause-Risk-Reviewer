"""SQLAlchemy ORM models — every persistent table in the system.

Importing this module is enough to populate ``Base.metadata``, which is what
Alembic autogenerate diffs against the live database.

Only long-lived data lives here. Uploaded contract *text* is the exception: it
is deleted as soon as the report is produced (see
``app.services.review.ReviewService``) and never reaches a table.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.config import get_settings
from app.database import Base

__all__ = ["AuditOverride", "Base", "ContractReport", "PlaybookEmbedding", "User"]

# JSONB on Postgres, plain JSON everywhere else. The tests run against SQLite,
# which has no JSONB; the variant keeps one model definition working on both.
_JSON = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    """A signed-in user, keyed by their Google identity."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Google "sub" claim
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditOverride(Base):
    """One human decision about an automated assessment.

    Append-only and retained indefinitely: this is the accountability record
    for every time a person disagreed with the pipeline or signed off on it.
    Read/write goes through :class:`~app.repositories.audit.AuditRepository`.

    The table is named for overrides because that is all it held at first. It
    now also carries acceptances (``action``), which leave ``old_risk`` and
    ``new_risk`` equal — the reviewer changed nothing, they vouched for it.
    """

    __tablename__ = "audit_overrides"

    id = Column(String, primary_key=True)
    report_id = Column(String, nullable=False, index=True)
    clause_id = Column(String, nullable=False)
    # override | accept | unaccept. Defaulted server-side so rows written
    # before acceptances existed read back as what they were.
    action = Column(String, nullable=False, server_default="override")
    old_risk = Column(String, nullable=False)
    new_risk = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ContractReport(Base):
    """A generated review report, kept for as long as its owner wants it.

    Reports used to live only in Redis under a retention TTL, which made the
    history list "everything from the last few hours" — a reviewer who came
    back the next day found their work gone and had to pay for the whole
    pipeline again. This table is the durable home; Redis is still selectable
    via ``REPORT_STORAGE`` for a throwaway/ephemeral deployment.

    ``payload`` holds the whole :class:`~app.schemas.ContractReviewReport` as
    JSON. The columns beside it are denormalized copies of the few fields the
    history list renders, so drawing a sidebar reads short rows instead of
    deserializing every clause of every report the user has ever run.
    """

    __tablename__ = "contract_reports"

    report_id = Column(String, primary_key=True)
    # The owner's Google ``sub``. Every read is filtered by it - a report id is
    # unguessable, but that is not access control. Indexed by the composite
    # below rather than on its own; ``session_id`` is that index's leftmost
    # column, so a second one would be dead weight on every write.
    session_id = Column(String, nullable=False)
    contract_id = Column(String, nullable=False)
    filename = Column(String, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
    # Bumped by overrides and acceptances; ``created_at`` stays the review date
    # so history keeps a stable order no matter how often a report is edited.
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    overall_risk = Column(String, nullable=False)
    summary = Column(_JSON, nullable=False, default=dict)
    clause_count = Column(Integer, nullable=False, default=0)
    payload = Column(_JSON, nullable=False)

    # History is always "this session's reports, newest first" - one composite
    # index answers it without a sort.
    __table_args__ = (Index("ix_contract_reports_session_created", "session_id", "created_at"),)


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
