"""Dependency-injection providers: DB session, vector store, LLM client."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.agents.judge import Judge
    from app.agents.orchestrator import Orchestrator
    from app.llm.client import LLMClient
    from app.rag.embedder import Embedder
    from app.rag.retriever import Retriever
    from app.rag.vector_store import VectorStore
    from app.repositories.contract_repo import ContractRepository
    from app.repositories.report_repo import ReportRepository
    from app.schemas.playbook import PlaybookPosition
    from app.services.eval_service import EvalService
    from app.services.override_service import OverrideService
    from app.services.review_service import ReviewService

_settings = get_settings()
_PLAYBOOK_PATH = "data/playbook/positions.yaml"

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Yield a scoped SQLAlchemy session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def get_llm_client() -> LLMClient:
    """Return the shared LLM client wrapper."""
    from app.llm.client import LLMClient

    return LLMClient()


@lru_cache
def get_embedder() -> Embedder:
    """Return the shared embedder."""
    from app.rag.embedder import GeminiEmbedder

    return GeminiEmbedder()


@lru_cache
def get_vector_store() -> VectorStore:
    """Return the configured vector store adapter."""
    from app.rag.vector_store import PgVectorStore

    return PgVectorStore(_settings.database_url)


@lru_cache
def get_retriever() -> Retriever:
    """Return the shared hybrid retriever."""
    from app.rag.retriever import Retriever

    return Retriever(get_embedder(), get_vector_store())


@lru_cache
def get_contract_repo() -> ContractRepository:
    """Return the process-wide in-memory contract store."""
    from app.repositories.contract_repo import ContractRepository

    return ContractRepository()


@lru_cache
def get_report_repo() -> ReportRepository:
    """Return the process-wide in-memory report store."""
    from app.repositories.report_repo import ReportRepository

    return ReportRepository()


@lru_cache
def get_known_positions() -> dict[str, PlaybookPosition]:
    """Return every playbook position keyed by id (used by the judge for grounding)."""
    from app.rag.ingest import load_positions

    return {position.id: position for position in load_positions(_PLAYBOOK_PATH)}


@lru_cache
def get_judge() -> Judge:
    """Return the shared grounding judge."""
    from app.agents.judge import Judge

    return Judge(get_llm_client(), get_known_positions())


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Build the shared segment -> classify -> match -> score -> judge pipeline."""
    from app.agents.classifier import Classifier
    from app.agents.matcher import Matcher
    from app.agents.orchestrator import Orchestrator
    from app.agents.risk_scorer import RiskScorer
    from app.agents.segmenter import Segmenter

    llm = get_llm_client()
    return Orchestrator(
        segmenter=Segmenter(llm),
        classifier=Classifier(llm),
        matcher=Matcher(llm, get_retriever()),
        risk_scorer=RiskScorer(llm),
        judge=get_judge(),
    )


@lru_cache
def get_review_service() -> ReviewService:
    """Return the shared review service."""
    from app.services.review_service import ReviewService

    return ReviewService(get_orchestrator(), get_contract_repo(), get_report_repo())


def get_override_service(db: Session = Depends(get_db)) -> OverrideService:
    """Return an override service bound to a request-scoped DB session."""
    from app.repositories.audit_repo import AuditRepository
    from app.services.override_service import OverrideService

    return OverrideService(get_report_repo(), AuditRepository(db))


def get_eval_service() -> EvalService:
    """Return an evaluation service."""
    from app.services.eval_service import EvalService

    return EvalService()
