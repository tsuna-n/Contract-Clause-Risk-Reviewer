from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt

from auth.config import auth_settings


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=auth_settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire, **(extra_claims or {})}
    return jwt.encode(
        payload, auth_settings.jwt_secret_key, algorithm=auth_settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
