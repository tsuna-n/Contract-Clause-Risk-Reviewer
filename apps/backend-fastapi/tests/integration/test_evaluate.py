"""Integration tests for ``POST /evaluate``.

The endpoint was public until 2026-07-30, which made it two things at once: a
way to spend the project's LLM quota a whole gold set at a time, and — through
``gold_set_path`` — a way to point the server at a file of the caller's
choosing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_eval_service
from app.main import create_app
from app.models import User
from app.services.evaluation import EvalService


class _ExplodingOrchestrator:
    """Reaching the pipeline in these tests would mean real LLM calls."""

    def review(self, *_args, **_kwargs):
        raise AssertionError("the eval harness ran; the request should have been refused first")


def _app() -> tuple:
    app = create_app()
    service = EvalService(_ExplodingOrchestrator(), known_position_ids=set())
    app.dependency_overrides[get_eval_service] = lambda: service
    return app, service


@pytest.fixture()
def client() -> TestClient:
    app, _ = _app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="user-1", email="reviewer@example.com", name="Reviewer"
    )
    return TestClient(app)


@pytest.fixture()
def anonymous_client() -> TestClient:
    app, _ = _app()
    return TestClient(app)


def test_evaluate_requires_auth(anonymous_client: TestClient) -> None:
    response = anonymous_client.post("/evaluate", json={"limit": 1})
    assert response.status_code == 401


def test_a_gold_set_path_outside_the_gold_directory_is_refused(client: TestClient) -> None:
    """Signing in buys the right to run an evaluation, not to read the disk."""
    response = client.post("/evaluate", json={"gold_set_path": "../../.env", "limit": 1})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_input"
