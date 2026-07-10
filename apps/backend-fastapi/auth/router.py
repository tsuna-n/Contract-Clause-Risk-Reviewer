import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth.config import auth_settings
from auth.jwt import create_access_token, decode_access_token
from auth.oauth import oauth
from auth.schemas import UserOut
from database import get_db
from models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer(auto_error=False)


@router.get("/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(
        request, auth_settings.google_redirect_uri
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s: %s", exc.error, exc.description)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {exc.error}",
        )

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
    return RedirectResponse(
        f"{auth_settings.frontend_url}/auth/callback?token={access_token}"
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout():
    return {"message": "Logged out. Discard the access token client-side."}
