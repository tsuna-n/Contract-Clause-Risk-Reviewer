"""Persistent audit log for human overrides.

Unlike contract/report stores, the override audit log must be retained
permanently for accountability.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.api.deps import Base
from app.schemas.taxonomy import RiskLevel


@dataclass
class OverrideRecord:
    """A single human override of an automated assessment."""

    report_id: str
    clause_id: str
    old_risk: RiskLevel
    new_risk: RiskLevel
    reason: str
    actor: str
    created_at: datetime


class AuditOverride(Base):
    """ORM model backing :class:`AuditRepository` (table: ``audit_overrides``)."""

    __tablename__ = "audit_overrides"

    id = Column(String, primary_key=True)
    report_id = Column(String, nullable=False, index=True)
    clause_id = Column(String, nullable=False)
    old_risk = Column(String, nullable=False)
    new_risk = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditRepository:
    """Append-only store for override records (backed by Postgres)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, record: OverrideRecord) -> None:
        """Persist an override record permanently."""
        row = AuditOverride(
            id=uuid.uuid4().hex,
            report_id=record.report_id,
            clause_id=record.clause_id,
            old_risk=record.old_risk.value,
            new_risk=record.new_risk.value,
            reason=record.reason,
            actor=record.actor,
            created_at=record.created_at,
        )
        self.db.add(row)
        self.db.commit()

    def list_for_report(self, report_id: str) -> list[OverrideRecord]:
        """Return all override records for a report, ordered by ``created_at``."""
        rows = (
            self.db.query(AuditOverride)
            .filter(AuditOverride.report_id == report_id)
            .order_by(AuditOverride.created_at)
            .all()
        )
        return [
            OverrideRecord(
                report_id=row.report_id,
                clause_id=row.clause_id,
                old_risk=RiskLevel(row.old_risk),
                new_risk=RiskLevel(row.new_risk),
                reason=row.reason,
                actor=row.actor,
                created_at=row.created_at,
            )
            for row in rows
        ]
