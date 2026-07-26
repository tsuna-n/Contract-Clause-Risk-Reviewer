"""FastAPI dependencies — the one place where the object graph is wired up.

Everything below is a ``Depends()`` target. The ``@lru_cache`` providers build
process-wide singletons (LLM client, retriever, repositories, the agent
pipeline); the plain functions are request-scoped because they need the
request's DB session or bearer token.

Overriding any of these in ``app.dependency_overrides`` swaps out that whole
subtree, which is how the tests replace the LLM, Redis, and auth.
"""

from __future__ import annotations

from functools import lru_cache

import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.agents import Classifier, Judge, Matcher, RiskScorer, Segmenter
from app.ai.llm import LLMClient
from app.ai.pipeline import Orchestrator
from app.ai.retrieval import (
    Embedder,
    GeminiEmbedder,
    PgVectorStore,
    Retriever,
    VectorStore,
    load_positions,
)
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.repositories.audit import AuditRepository
from app.repositories.contract import ContractRepository, RedisContractRepository
from app.repositories.playbook import PlaybookRepository
from app.repositories.report import RedisReportRepository, ReportRepository
from app.schemas import PlaybookPosition
from app.security import decode_access_token
from app.services.evaluation import EvalService
from app.services.override import OverrideService
from app.services.playbook import PlaybookService
from app.services.review import ReviewService

PLAYBOOK_PATH = "data/playbook/positions.yaml"

_bearer_scheme = HTTPBearer(auto_error=False)


# --- auth --------------------------------------------------------------------


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token into the signed-in user, or raise ``401``."""
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


# --- infrastructure ----------------------------------------------------------


@lru_cache
def get_redis_client() -> redis.Redis:
    """Return the shared Redis client (contract/report repos, session state)."""
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def get_contract_repo() -> ContractRepository:
    """Return the shared Redis-backed contract store."""
    return RedisContractRepository(get_redis_client(), get_settings().retention_ttl_seconds)


@lru_cache
def get_report_repo() -> ReportRepository:
    """Return the shared Redis-backed report store."""
    return RedisReportRepository(get_redis_client(), get_settings().retention_ttl_seconds)


# --- llm + rag ---------------------------------------------------------------


@lru_cache
def get_llm_client() -> LLMClient:
    """Return the shared LLM client wrapper."""
    return LLMClient()


@lru_cache
def get_embedder() -> Embedder:
    """Return the shared embedder."""
    return GeminiEmbedder()


@lru_cache
def get_vector_store() -> VectorStore:
    """Return the configured vector store adapter."""
    return PgVectorStore()


@lru_cache
def get_retriever() -> Retriever:
    """Return the shared hybrid retriever."""
    return Retriever(get_embedder(), get_vector_store())


@lru_cache
def get_known_positions() -> dict[str, PlaybookPosition]:
    """Return every playbook position keyed by id (used by the judge for grounding)."""
    return {position.id: position for position in load_positions(PLAYBOOK_PATH)}


# --- pipeline ----------------------------------------------------------------


@lru_cache
def get_judge() -> Judge:
    """Return the shared grounding judge."""
    return Judge(get_llm_client(), get_known_positions())


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Build the shared segment -> classify -> match -> score -> judge pipeline."""
    llm = get_llm_client()
    return Orchestrator(
        segmenter=Segmenter(llm),
        classifier=Classifier(llm),
        matcher=Matcher(llm, get_retriever()),
        risk_scorer=RiskScorer(llm),
        judge=get_judge(),
    )


# --- services ----------------------------------------------------------------


@lru_cache
def get_review_service() -> ReviewService:
    """Return the shared review service."""
    return ReviewService(
        get_orchestrator(),
        get_contract_repo(),
        get_report_repo(),
        retention_ttl_seconds=get_settings().retention_ttl_seconds,
    )


def get_override_service(db: Session = Depends(get_db)) -> OverrideService:
    """Return an override service bound to a request-scoped DB session."""
    return OverrideService(get_report_repo(), AuditRepository(db))


def get_playbook_service(db: Session = Depends(get_db)) -> PlaybookService:
    """Return a playbook service bound to a request-scoped DB session.

    Request-scoped like the override service: each call gets its own session
    so a commit in one request can't bleed into another. The embedder is the
    shared singleton so newly created/updated positions get real vectors and
    turn up in retrieval immediately.
    """
    return PlaybookService(PlaybookRepository(db), get_embedder())


@lru_cache
def get_eval_service() -> EvalService:
    """Return the shared evaluation service."""
    return EvalService(get_orchestrator(), set(get_known_positions()))
