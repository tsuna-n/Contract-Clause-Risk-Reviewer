"""Application settings + feature flags (pydantic-settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration.

    Values are loaded from ``.env`` (see ``.env.example``). Extra keys are
    ignored so the same file can be shared with other tooling.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- core ---
    database_url: str
    app_env: str = "development"

    # --- auth / oauth (kept from the existing backend; optional) ---
    google_oauth_api: str | None = None
    google_key_secret: str | None = None
    google_redirect_uri: str | None = None
    frontend_url: str | None = None
    session_secret_key: str | None = None
    jwt_secret_key: str | None = None

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
