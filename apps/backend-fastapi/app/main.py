"""FastAPI application factory: lifespan, CORS, router wiring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logger import configure_logging
from app.routes import api_router
from app.security import SESSION_COOKIE_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hooks."""
    configure_logging()
    # Schema (tables + the ``vector`` extension) is owned by Alembic now -
    # run `alembic upgrade head` before starting the app. See
    # apps/backend-fastapi/README.md.
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Contract Clause Risk Reviewer", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Required by Authlib's OAuth redirect flow to persist state across requests.
    # The cookie name is pinned so /auth/logout can delete the same cookie.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie=SESSION_COOKIE_NAME,
    )

    app.include_router(api_router)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"service": "contract-reviewer", "status": "ok"}

    return app


app = create_app()
