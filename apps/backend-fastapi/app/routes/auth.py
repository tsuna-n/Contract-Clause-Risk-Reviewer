"""Auth endpoints: Google OAuth login/callback + the current-user probe."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import UserOut
from app.security import SESSION_COOKIE_NAME, create_access_token, oauth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _redirect_to_frontend(path: str, **params: str) -> RedirectResponse:
    """Redirect the browser back to the frontend.

    The OAuth endpoints are reached by full-page navigation, not by fetch(),
    so a failure here has to hand the browser somewhere a person can act on.
    Returning a JSON error would strand the user on a blank API response with
    no way back to the login screen.
    """
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{get_settings().frontend_url}{path}{query}")


@router.get("/google/login")
async def google_login(request: Request):
    """Kick off the Google OAuth flow."""
    return await oauth.google.authorize_redirect(request, get_settings().google_redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Complete the OAuth flow: upsert the user and hand a JWT to the frontend.

    Every exit from here is a redirect back to the frontend — with a token on
    success, or with an ``error`` code the login page renders on failure
    (``access_denied`` when the user cancels at Google's consent screen,
    ``mismatching_state`` when the session cookie was lost mid-flow).
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s: %s", exc.error, exc.description)
        return _redirect_to_frontend("/login", error=exc.error or "oauth_failed")

    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        logger.warning("Google OAuth returned no usable userinfo: %s", sorted(token))
        return _redirect_to_frontend("/login", error="missing_email")

    user_id = userinfo["sub"]  # Google's stable per-account identifier
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=userinfo["email"])
        db.add(user)

    user.email = userinfo["email"]
    user.name = userinfo.get("name")
    user.picture = userinfo.get("picture")
    db.commit()

    return _redirect_to_frontend("/auth/callback", token=create_access_token(subject=user_id))


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user behind the bearer token."""
    return current_user


@router.post("/logout")
def logout(request: Request) -> Response:
    """Log out: drop the server-side session and the cookie that carries it.

    The access token is a stateless JWT, so discarding it client-side is what
    ends the session — but the OAuth flow also leaves a signed ``session``
    cookie in the browser (``SessionMiddleware``, which authlib uses to hold
    the CSRF state across the redirect to Google). Leaving that behind means a
    "logged out" browser still walks around carrying server-issued state, and
    the next login reuses it. Clear both halves here.
    """
    request.session.clear()

    response = JSONResponse({"message": "Logged out. Discard the access token client-side."})
    # SessionMiddleware only emits an expiry cookie when the session it loaded
    # was non-empty, so deleting it explicitly is what makes logout
    # deterministic for a browser whose session cookie is stale or unreadable.
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
