"""Auth endpoints: Google OAuth login/callback + the current-user probe."""

from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import create_access_token, oauth
from app.models import User
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/login")
async def google_login(request: Request):
    """Kick off the Google OAuth flow."""
    return await oauth.google.authorize_redirect(request, get_settings().google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Complete the OAuth flow: upsert the user and hand a JWT to the frontend."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s: %s", exc.error, exc.description)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {exc.error}",
        ) from exc

    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not fetch user info from Google",
        )

    user = db.get(User, userinfo["sub"])
    if user is None:
        user = User(id=userinfo["sub"], email=userinfo["email"])
        db.add(user)

    user.email = userinfo["email"]
    user.name = userinfo.get("name")
    user.picture = userinfo.get("picture")
    db.commit()

    access_token = create_access_token(subject=user.id)
    return RedirectResponse(f"{get_settings().frontend_url}/auth/callback?token={access_token}")


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user behind the bearer token."""
    return current_user


@router.post("/logout")
def logout() -> dict[str, str]:
    """Stateless logout: the client just discards its token."""
    return {"message": "Logged out. Discard the access token client-side."}
