"""The ``audit_overrides`` table — permanent log of human risk overrides.

Unlike contracts and reports (session-scoped, Redis, TTL'd), this log is
retained indefinitely for accountability. Read/write goes through
:class:`~app.repositories.audit_repo.AuditRepository`.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.core.db import Base


class AuditOverride(Base):
    """A single human override of an automated assessment."""

    __tablename__ = "audit_overrides"

    id = Column(String, primary_key=True)
    report_id = Column(String, nullable=False, index=True)
    clause_id = Column(String, nullable=False)
    old_risk = Column(String, nullable=False)
    new_risk = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
