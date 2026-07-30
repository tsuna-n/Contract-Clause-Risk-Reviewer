"""Persistent audit log for human decisions on a review.

Overrides and acceptances both land here, and unlike the reports they describe
this log is never deleted: it is the record of who took responsibility for
which assessment.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from app.models import AuditOverride
from app.schemas import RiskLevel


class AuditAction(StrEnum):
    """What the reviewer did to the clause."""

    OVERRIDE = "override"  # Replaced the machine's risk level with their own.
    ACCEPT = "accept"  # Signed off on the assessment as it stands.
    UNACCEPT = "unaccept"  # Withdrew a previous sign-off.


@dataclass
class OverrideRecord:
    """One human decision about an automated assessment.

    For an acceptance, ``old_risk`` and ``new_risk`` are both the risk level in
    force at the time — nothing changed, and the record says which assessment
    was vouched for.
    """

    report_id: str
    clause_id: str
    old_risk: RiskLevel
    new_risk: RiskLevel
    reason: str
    actor: str
    created_at: datetime
    action: AuditAction = AuditAction.OVERRIDE


class AuditRepository:
    """Append-only store for reviewer decisions (backed by Postgres)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, record: OverrideRecord) -> None:
        """Persist a decision record permanently."""
        row = AuditOverride(
            id=uuid.uuid4().hex,
            report_id=record.report_id,
            clause_id=record.clause_id,
            action=record.action.value,
            old_risk=record.old_risk.value,
            new_risk=record.new_risk.value,
            reason=record.reason,
            actor=record.actor,
            created_at=record.created_at,
        )
        self.db.add(row)
        self.db.commit()

    def list_for_report(self, report_id: str) -> list[OverrideRecord]:
        """Return all decision records for a report, ordered by ``created_at``."""
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
                action=AuditAction(row.action),
                old_risk=RiskLevel(row.old_risk),
                new_risk=RiskLevel(row.new_risk),
                reason=row.reason,
                actor=row.actor,
                created_at=row.created_at,
            )
            for row in rows
        ]
