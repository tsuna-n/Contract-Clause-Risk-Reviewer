"""Integration tests for Playbook CRUD endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_playbook_service
from app.main import create_app
from app.models import PlaybookEmbedding, User
from app.services.playbook import PlaybookService


class MemoryPlaybookRepository:
    def __init__(self) -> None:
        self.data: dict[str, PlaybookEmbedding] = {}

    def list_all(self, clause_type: str | None = None) -> list[PlaybookEmbedding]:
        items = list(self.data.values())
        if clause_type:
            items = [item for item in items if item.clause_type == clause_type]
        return items

    def get_by_id(self, position_id: str) -> PlaybookEmbedding | None:
        return self.data.get(position_id)

    def create(
        self, payload, embedding: list[float] | None = None
    ) -> PlaybookEmbedding:
        pos_id = payload.id or "pb_mock_1"
        row = PlaybookEmbedding(
            id=pos_id,
            clause_type=payload.clause_type.value,
            title=payload.title,
            preferred_language=payload.preferred_language,
            fallback_language=payload.fallback_language,
            risk_if_absent=payload.risk_if_absent.value,
            tags=payload.tags,
            embedding=embedding or [0.0] * 768,
        )
        self.data[pos_id] = row
        return row

    def update(
        self, position_id: str, payload, embedding: list[float] | None = None
    ) -> PlaybookEmbedding | None:
        row = self.get_by_id(position_id)
        if row is None:
            return None
        if payload.title is not None:
            row.title = payload.title
        if payload.risk_if_absent is not None:
            row.risk_if_absent = payload.risk_if_absent.value
        return row

    def delete(self, position_id: str) -> bool:
        if position_id in self.data:
            del self.data[position_id]
            return True
        return False


def _app_with_playbook_service():
    app = create_app()
    repo = MemoryPlaybookRepository()
    service = PlaybookService(repo, embedder=None)
    app.dependency_overrides[get_playbook_service] = lambda: service
    return app


@pytest.fixture()
def client() -> TestClient:
    app = _app_with_playbook_service()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="user-1", email="reviewer@example.com", name="Reviewer"
    )
    return TestClient(app)


@pytest.fixture()
def anonymous_client() -> TestClient:
    """A client with no bearer token, to prove the router's auth actually bites."""
    return TestClient(_app_with_playbook_service())


def test_playbook_crud_lifecycle(client: TestClient):
    # 1. Create a new position (Create)
    create_payload = {
        "id": "pb_test_crud_01",
        "clause_type": "confidentiality",
        "title": "Test Confidentiality Position",
        "preferred_language": "Information shall remain strictly confidential for 3 years.",
        "fallback_language": "Information shall remain confidential for 1 year.",
        "risk_if_absent": "high",
        "tags": ["test", "confidentiality"],
    }
    res = client.post("/playbook", json=create_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "pb_test_crud_01"
    assert data["title"] == "Test Confidentiality Position"
    assert data["clause_type"] == "confidentiality"

    # 2. Get single position (Read Single)
    res = client.get("/playbook/pb_test_crud_01")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test Confidentiality Position"

    # 3. List all positions (Read All)
    res = client.get("/playbook?clause_type=confidentiality")
    assert res.status_code == 200
    items = res.json()
    assert any(i["id"] == "pb_test_crud_01" for i in items)

    # 4. Update position (Update)
    update_payload = {
        "title": "Updated Confidentiality Position",
        "risk_if_absent": "medium",
    }
    res = client.put("/playbook/pb_test_crud_01", json=update_payload)
    assert res.status_code == 200
    updated_data = res.json()
    assert updated_data["title"] == "Updated Confidentiality Position"
    assert updated_data["risk_if_absent"] == "medium"

    # 5. Delete position (Delete)
    res = client.delete("/playbook/pb_test_crud_01")
    assert res.status_code == 204

    # 6. Verify non-existence after deletion
    res = client.get("/playbook/pb_test_crud_01")
    assert res.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/playbook"),
        ("get", "/playbook/search?q=liability"),
        ("get", "/playbook/pb_1"),
        ("post", "/playbook"),
        ("put", "/playbook/pb_1"),
        ("delete", "/playbook/pb_1"),
    ],
)
def test_every_playbook_endpoint_requires_auth(anonymous_client, method, path) -> None:
    """All six were public until 2026-07-30.

    Parametrized over every route rather than spot-checking one, because the
    hole was not a wrong check - it was a missing one, on endpoints nobody
    thought to look at. The write methods are the sharp end: the playbook is
    what the judge grounds citations against, so editing it edits every verdict
    the system will reach.
    """
    body = {"json": {}} if method in {"post", "put"} else {}
    response = anonymous_client.request(method, path, **body)
    assert response.status_code == 401
