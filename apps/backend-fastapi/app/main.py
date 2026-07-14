"""FastAPI application factory: lifespan, CORS, router wiring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hooks."""
    configure_logging()
    # TODO: warm caches, verify vector store connectivity.
    yield
    # TODO: graceful shutdown (flush audit log, close pools).


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Contract Clause Risk Reviewer", version="0.1.0", lifespan=lifespan)

    allowed_origins = [settings.frontend_url] if settings.frontend_url else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    # TODO: mount contracts/playbook/evaluate routers (see api.v1).

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"service": "contract-reviewer", "status": "ok"}

    return app


app = create_app()
