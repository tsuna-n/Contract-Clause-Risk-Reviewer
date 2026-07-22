"""Shared fixtures for integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """An isolated in-memory SQLite session containing just the ``users`` table.

    Auth tests only ever touch ``users``, so we skip the Postgres-only
    ``playbook_embeddings`` table (its ``vector`` column type has no SQLite
    equivalent) and get a fast, hermetic session with no real DB dependency.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
