"""Health / readiness endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict[str, str]:
    """Readiness probe for the PostgreSQL connection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surfaced as 503
        raise HTTPException(status_code=503, detail="Database not connected") from exc
    return {"status": "ok", "database": "connected"}
