"""Persistent audit log for human overrides.

Unlike contract/report stores, the override audit log must be retained
permanently for accountability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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


class AuditRepository:
    """Append-only store for override records (backed by Postgres)."""

    def append(self, record: OverrideRecord) -> None:
        """Persist an override record permanently.

        TODO: insert into an ``audit_overrides`` table via SQLAlchemy.
        """
        raise NotImplementedError

    def list_for_report(self, report_id: str) -> list[OverrideRecord]:
        """Return all override records for a report.

        TODO: query by ``report_id`` ordered by ``created_at``.
        """
        raise NotImplementedError
