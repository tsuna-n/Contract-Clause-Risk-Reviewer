"""FastAPI application factory: lifespan, CORS, router wiring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import contracts, evaluate, health, playbook
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from auth.config import auth_settings
from auth.router import router as auth_router


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

    allowed_origins = [settings.frontend_url] if settings.frontend_url else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Required by Authlib's OAuth redirect flow to persist state across requests.
    app.add_middleware(SessionMiddleware, secret_key=auth_settings.session_secret_key)

    app.include_router(health.router)
    app.include_router(contracts.router)
    app.include_router(playbook.router)
    app.include_router(evaluate.router)
    app.include_router(auth_router)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"service": "contract-reviewer", "status": "ok"}

    return app


app = create_app()
