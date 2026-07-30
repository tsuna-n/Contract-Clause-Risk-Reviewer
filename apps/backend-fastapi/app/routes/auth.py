"""Auth endpoints: Google OAuth login/callback + the current-user probe."""

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse

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


def _frontend_base_url(request: Request | None) -> str:
    """Where to send the browser back to.

    Normally ``FRONTEND_URL``. The ``Referer`` is allowed to override the
    *port* only - and only when it names the same host the request arrived on
    - so that opening the app over the LAN works without editing
    ``FRONTEND_URL`` every time the dev machine's address changes.

    The host check is the whole point. This helper appends a freshly minted
    JWT to the URL it returns, so trusting ``Referer`` outright would let any
    page on the internet link to ``/auth/dev-login`` (or start the Google flow)
    and have the token delivered straight to its own domain. ``Referer`` is
    attacker-controlled; the host the request was addressed to is not.
    """
    configured = get_settings().frontend_url
    if request is None:
        return configured

    referer = request.headers.get("referer")
    if not referer:
        return configured

    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return configured
    # Same host as the API call itself -> it really is this deployment's
    # frontend on another port. Anything else is someone else's origin.
    if parsed.hostname != request.url.hostname:
        logger.warning(
            "ignoring cross-origin referer %r on %s (expected host %r)",
            parsed.netloc,
            request.url.path,
            request.url.hostname,
        )
        return configured
    return f"{parsed.scheme}://{parsed.netloc}"


def _redirect_to_frontend(request: Request | None, path: str, **params: str) -> RedirectResponse:
    """Redirect the browser back to the frontend.

    The OAuth endpoints are reached by full-page navigation, not by fetch(),
    so a failure here has to hand the browser somewhere a person can act on.
    Returning a JSON error would strand the user on a blank API response with
    no way back to the login screen.
    """
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{_frontend_base_url(request)}{path}{query}")


@router.get("/dev-login")
def dev_login(
    request: Request,
    email: str = "dev@example.com",
    name: str = "Dev User",
    db: Session = Depends(get_db),
):
    """Fast dev sign-in for LAN/offline testing, where Google OAuth can't work.

    This hands out a token for whatever email is asked for, with no proof of
    anything - so it is behind two locks that must both be open
    (``APP_ENV=development`` *and* ``ENABLE_DEV_LOGIN=true``). One lock would be
    ``APP_ENV``, which is also the variable most likely to be left at its
    default on the deployment where that matters most.
    """
    settings = get_settings()
    if settings.app_env != "development" or not settings.enable_dev_login:
        return _redirect_to_frontend(request, "/login", error="dev_login_disabled")

    user_id = f"dev-user-{email}"
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=email)
        db.add(user)

    user.email = email
    user.name = name
    user.picture = None
    db.commit()

    return _redirect_to_frontend(
        request, "/auth/callback", token=create_access_token(subject=user_id)
    )


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
        return _redirect_to_frontend(request, "/login", error=exc.error or "oauth_failed")

    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        logger.warning("Google OAuth returned no usable userinfo: %s", sorted(token))
        return _redirect_to_frontend(request, "/login", error="missing_email")

    user_id = userinfo["sub"]  # Google's stable per-account identifier
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=userinfo["email"])
        db.add(user)

    user.email = userinfo["email"]
    user.name = userinfo.get("name")
    user.picture = userinfo.get("picture")
    db.commit()

    return _redirect_to_frontend(
        request, "/auth/callback", token=create_access_token(subject=user_id)
    )


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
