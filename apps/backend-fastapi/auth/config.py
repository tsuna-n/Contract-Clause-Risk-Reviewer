from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    google_oauth_api: str
    google_key_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    frontend_url: str = "http://localhost:5173"

    session_secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    class Config:
        env_file = ".env"
        extra = "ignore"


auth_settings = AuthSettings()  # type: ignore
