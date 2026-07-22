"""FastAPI application factory: lifespan, CORS, router wiring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, contracts, evaluate, health, playbook
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


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
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

    for module in (health, auth, contracts, playbook, evaluate):
        app.include_router(module.router)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"service": "contract-reviewer", "status": "ok"}

    return app


app = create_app()
