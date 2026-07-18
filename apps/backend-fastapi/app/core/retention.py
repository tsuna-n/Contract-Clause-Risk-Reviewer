"""Session TTL / no-retention policy helpers.

Uploaded contracts are session-scoped and must not be persisted beyond the
configured TTL (see spec item on data retention). Override/audit logs are the
only long-lived artifacts.
"""

from __future__ import annotations


def session_ttl_seconds() -> int:
    """Return the configured session TTL in seconds."""
    from app.core.config import get_settings

    return get_settings().retention_ttl_seconds


def enforce_retention(session_id: str) -> int:
    """Purge ``session_id``'s reports older than the TTL; return how many were purged.

    Uploaded contracts are deleted from :class:`ContractRepository` as soon as
    their review report is produced (see ``ReviewService``), so the only
    long-lived session-scoped state left to sweep is the report store.
    """
    from app.api.deps import get_report_repo

    reports = get_report_repo()
    return len(reports.purge_expired(session_id, session_ttl_seconds()))
