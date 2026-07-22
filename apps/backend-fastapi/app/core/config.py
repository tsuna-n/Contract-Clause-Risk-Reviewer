"""Application settings + feature flags (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration — the single source of truth.

    Values are loaded from ``.env`` (see ``.env.example``). Extra keys are
    ignored so the same file can be shared with other tooling. Fields without
    a default are required: the app refuses to boot rather than run with a
    missing database URL or a placeholder signing key.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- core ---
    database_url: str
    app_env: str = "development"
    # Origin of the frontend: doubles as the CORS allow-list and as the
    # redirect target after a successful OAuth callback.
    frontend_url: str = "http://localhost:5173"

    # --- auth: Google OAuth + JWT ---
    google_oauth_api: str
    google_key_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    session_secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- llm (Google GenAI / Gemini) ---
    gemini_api_key: str | None = None  # read from $GEMINI_API_KEY
    llm_model: str = "gemini-3.5-flash"

    # --- rag / storage ---
    redis_url: str = "redis://localhost:6379/0"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # --- feature flags ---
    enable_judge: bool = True
    enable_hybrid_retrieval: bool = True
    retention_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()  # type: ignore[call-arg]
