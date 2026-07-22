"""Authentication primitives: JWT signing/verification + the Google OAuth client.

The endpoints that use these live in ``app.api.auth``; the dependency that
turns a bearer token into a :class:`~app.models.user.User` is
``app.api.deps.get_current_user``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import get_settings

_settings = get_settings()

oauth = OAuth()
oauth.register(
    name="google",
    client_id=_settings.google_oauth_api,
    client_secret=_settings.google_key_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Sign a JWT for ``subject`` (the Google ``sub`` claim, i.e. our user id)."""
    expire = datetime.now(UTC) + timedelta(minutes=_settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, **(extra_claims or {})}
    return jwt.encode(payload, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify a JWT and return its claims, or raise ``401``."""
    try:
        return jwt.decode(
            token,
            _settings.jwt_secret_key,
            algorithms=[_settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
