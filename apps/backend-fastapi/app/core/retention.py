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


def enforce_retention(session_id: str) -> None:
    """Purge any session-scoped data older than the TTL.

    TODO: sweep contract/report repositories for expired session data.
    """
    raise NotImplementedError
