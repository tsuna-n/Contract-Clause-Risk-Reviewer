"""Integration tests for ``/auth/*`` - JWT verification and the Google OAuth flow.

The OAuth tests mock authlib's client (``oauth.google``) rather than hitting
Google's real servers: this environment has no outbound network access, and a
genuinely live login also requires a human to click through Google's consent
screen with a real account - not something that can run in an automated
suite. Mocking at the authlib boundary still exercises all of *our* code for
both endpoints - redirect wiring, user upsert, JWT issuance, and every error
path - which is what's actually ours to verify.
"""

from __future__ import annotations

import pytest
from authlib.integrations.starlette_client import OAuthError
from fastapi.testclient import TestClient
from starlette.responses import RedirectResponse

from app.api.deps import get_db
from app.main import create_app
from auth.config import auth_settings
from auth.jwt import create_access_token, decode_access_token
from auth.oauth import oauth
from models import User


@pytest.fixture()
def client(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# --- JWT-protected /auth/me -------------------------------------------------


def test_me_with_valid_token_returns_user(client: TestClient, db_session) -> None:
    user = User(id="google-sub-1", email="alice@example.com", name="Alice")
    db_session.add(user)
    db_session.commit()

    token = create_access_token(subject=user.id)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "google-sub-1"
    assert body["email"] == "alice@example.com"


def test_me_without_token_is_401(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_bogus_token_is_401(client: TestClient) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_me_with_token_for_unknown_user_is_401(client: TestClient) -> None:
    token = create_access_token(subject="no-such-user")
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# --- /auth/google/login ------------------------------------------------------


def test_google_login_redirects_with_configured_redirect_uri(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called_with = {}

    async def fake_authorize_redirect(request, redirect_uri):
        called_with["redirect_uri"] = redirect_uri
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?mock=1")

    monkeypatch.setattr(oauth.google, "authorize_redirect", fake_authorize_redirect)

    resp = client.get("/auth/google/login", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert called_with["redirect_uri"] == auth_settings.google_redirect_uri
    assert resp.headers["location"].startswith("https://accounts.google.com/")


# --- /auth/google/callback ----------------------------------------------------


def _mock_token(
    email: str = "bob@example.com",
    sub: str = "google-sub-2",
    name: str = "Bob",
    picture: str | None = None,
) -> dict:
    return {"userinfo": {"sub": sub, "email": email, "name": name, "picture": picture}}


def test_google_callback_creates_new_user_and_issues_jwt(
    client: TestClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_authorize_access_token(request):
        return _mock_token()

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake_authorize_access_token)

    resp = client.get("/auth/google/callback", follow_redirects=False)

    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert location.startswith(f"{auth_settings.frontend_url}/auth/callback?token=")

    token = location.split("token=", 1)[1]
    payload = decode_access_token(token)
    assert payload["sub"] == "google-sub-2"

    user = db_session.get(User, "google-sub-2")
    assert user is not None
    assert user.email == "bob@example.com"
    assert user.name == "Bob"


def test_google_callback_updates_existing_user(
    client: TestClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = User(id="google-sub-3", email="old@example.com", name="Old Name")
    db_session.add(existing)
    db_session.commit()

    async def fake_authorize_access_token(request):
        return _mock_token(email="new@example.com", sub="google-sub-3", name="New Name")

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake_authorize_access_token)

    client.get("/auth/google/callback", follow_redirects=False)

    db_session.refresh(existing)
    assert existing.email == "new@example.com"
    assert existing.name == "New Name"


def test_google_callback_oauth_error_is_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_authorize_access_token(request):
        raise OAuthError(error="access_denied", description="user cancelled")

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake_authorize_access_token)

    resp = client.get("/auth/google/callback")

    assert resp.status_code == 400


def test_google_callback_missing_email_is_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_authorize_access_token(request):
        return {"userinfo": {"sub": "google-sub-4"}}  # no email

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake_authorize_access_token)

    resp = client.get("/auth/google/callback")

    assert resp.status_code == 400
