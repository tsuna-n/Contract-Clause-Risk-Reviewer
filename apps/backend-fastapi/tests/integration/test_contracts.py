"""Integration tests for the ``/contracts`` endpoints.

Covers ``/review``, the history reads (``GET /contracts`` and
``GET /contracts/{id}``) and ``/{id}/override``.

The LLM/RAG pipeline (``Orchestrator``) and the contract/report repos are
replaced with fast in-process fakes rather than a real Gemini + Redis, and
auth is overridden with a fixed user - mocking auth + DB + LLM, same as
called out as future work in the backend README. What's under test is
strictly the request/response contract of these two endpoints: auth
enforcement, request -> service wiring, risk aggregation after an override,
the audit trail it writes, and error mapping (404/422).
"""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import (
    get_current_user,
    get_override_service,
    get_report_service,
    get_review_service,
)
from app.main import create_app
from app.models import AuditOverride, Base, User
from app.parsers import ParsedDocument
from app.repositories.audit import AuditRepository
from app.repositories.contract import InMemoryContractRepository
from app.repositories.report import InMemoryReportRepository
from app.schemas import (
    Clause,
    ClauseReview,
    ClauseType,
    ContractReviewReport,
    RiskLevel,
    RiskSummary,
    Span,
)
from app.services.override import OverrideService
from app.services.report import ReportService
from app.services.review import ReviewService

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class _FakeOrchestrator:
    """Stands in for the real segment -> classify -> match -> score -> judge pipeline."""

    def __init__(self) -> None:
        # Report ids have to differ across uploads or the history tests would
        # be asserting against one report saved twice.
        self._count = 0

    def review(
        self, document: ParsedDocument, *, contract_id: str, session_id: str
    ) -> ContractReviewReport:
        self._count += 1
        clause = Clause(
            id="clause-1",
            text="Either party may terminate this agreement for convenience.",
            span=Span(start=0, end=10, page=1),
            clause_type=ClauseType.TERMINATION,
        )
        review = ClauseReview(
            clause=clause,
            risk_level=RiskLevel.MEDIUM,
            rationale="No cure period before termination for convenience.",
            verified=True,
        )
        return ContractReviewReport(
            report_id=f"report-{self._count}",
            contract_id=contract_id,
            session_id=session_id,
            overall_risk=RiskLevel.MEDIUM,
            summary=RiskSummary(medium=1),
            reviews=[review],
        )


def _sample_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("1. Termination. Either party may terminate for convenience.")
    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture()
def audit_db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[AuditOverride.__table__])
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def current_user() -> User:
    return User(id="user-1", email="reviewer@example.com", name="Reviewer")


@pytest.fixture()
def client(audit_db_session: Session, current_user: User) -> TestClient:
    app = create_app()

    reports = InMemoryReportRepository()
    review_service = ReviewService(_FakeOrchestrator(), InMemoryContractRepository(), reports)
    override_service = OverrideService(reports, AuditRepository(audit_db_session))
    report_service = ReportService(reports)

    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_review_service] = lambda: review_service
    app.dependency_overrides[get_override_service] = lambda: override_service
    app.dependency_overrides[get_report_service] = lambda: report_service

    client = TestClient(app)
    # The repo is shared with the tests so they can plant another session's
    # report without going through an upload.
    client.report_repo = reports  # type: ignore[attr-defined]
    return client


def _upload(client: TestClient, *, filename: str = "contract.docx", content: bytes | None = None):
    return client.post(
        "/contracts/review",
        files={"file": (filename, content or _sample_docx_bytes(), _DOCX_CONTENT_TYPE)},
    )


# --- POST /contracts/review --------------------------------------------------


def test_review_contract_returns_report(client: TestClient) -> None:
    resp = _upload(client)

    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == "report-1"
    # The owning session is the user's Google ``sub``: kept on the model for
    # purging, withheld from the wire.
    assert "session_id" not in body
    assert body["overall_risk"] == "medium"
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["clause"]["clause_type"] == "termination"
    # Carried over from the upload - it's what the history list is labelled with.
    assert body["filename"] == "contract.docx"


def test_review_contract_requires_auth() -> None:
    client = TestClient(create_app())
    resp = _upload(client)
    assert resp.status_code == 401


def test_review_contract_accepts_plain_text(client: TestClient) -> None:
    resp = _upload(client, filename="contract.txt", content="ข้อ 1. การเลิกสัญญา".encode())

    assert resp.status_code == 200
    assert resp.json()["filename"] == "contract.txt"


def test_review_contract_rejects_unsupported_file_type(client: TestClient) -> None:
    resp = _upload(client, filename="contract.rtf", content=b"hello world")
    assert resp.status_code == 422


# --- GET /contracts (history) ------------------------------------------------


def test_history_lists_this_session_newest_first(client: TestClient) -> None:
    _upload(client, filename="first.docx")
    _upload(client, filename="second.docx")

    resp = client.get("/contracts")

    assert resp.status_code == 200
    rows = resp.json()
    assert [row["filename"] for row in rows] == ["second.docx", "first.docx"]
    # Summaries, not reports: the clause reviews are what GET /{id} is for.
    assert rows[0]["clause_count"] == 1
    assert "reviews" not in rows[0]
    assert rows[0]["overall_risk"] == "medium"


def test_history_is_empty_before_any_upload(client: TestClient) -> None:
    assert client.get("/contracts").json() == []


def test_history_excludes_other_sessions(client: TestClient) -> None:
    _upload(client, filename="mine.docx")
    client.report_repo.save(  # type: ignore[attr-defined]
        ContractReviewReport(
            report_id="someone-elses",
            contract_id="c",
            session_id="user-2",
            filename="theirs.docx",
        )
    )

    rows = client.get("/contracts").json()

    assert [row["filename"] for row in rows] == ["mine.docx"]


def test_history_requires_auth() -> None:
    assert TestClient(create_app()).get("/contracts").status_code == 401


# --- GET /contracts/{report_id} ----------------------------------------------


def test_get_report_returns_the_full_report(client: TestClient) -> None:
    report_id = _upload(client).json()["report_id"]

    resp = client.get(f"/contracts/{report_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == report_id
    assert len(body["reviews"]) == 1
    assert "session_id" not in body


def test_get_report_survives_an_override(client: TestClient) -> None:
    report = _upload(client).json()
    client.post(
        f"/contracts/{report['report_id']}/override",
        json={"clause_id": "clause-1", "new_risk": "high", "reason": "escalated"},
    )

    body = client.get(f"/contracts/{report['report_id']}").json()

    assert body["reviews"][0]["risk_level"] == "high"
    assert body["overall_risk"] == "high"


def test_get_unknown_report_is_404(client: TestClient) -> None:
    assert client.get("/contracts/no-such-report").status_code == 404


def test_get_another_sessions_report_is_404(client: TestClient) -> None:
    """Not 403: a 403 would confirm the id exists, which is the thing to hide."""
    client.report_repo.save(  # type: ignore[attr-defined]
        ContractReviewReport(report_id="someone-elses", contract_id="c", session_id="user-2")
    )

    assert client.get("/contracts/someone-elses").status_code == 404


def test_get_report_requires_auth() -> None:
    assert TestClient(create_app()).get("/contracts/report-1").status_code == 401


# --- POST /contracts/{report_id}/override -----------------------------------


def test_override_changes_risk_and_writes_audit(
    client: TestClient, audit_db_session: Session
) -> None:
    report = _upload(client).json()

    resp = client.post(
        f"/contracts/{report['report_id']}/override",
        json={
            "clause_id": report["reviews"][0]["clause"]["id"],
            "new_risk": "high",
            "reason": "escalated by legal",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["reviews"][0]["risk_level"] == "high"
    assert body["overall_risk"] == "high"

    audit_rows = (
        audit_db_session.query(AuditOverride).filter_by(report_id=report["report_id"]).all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].old_risk == "medium"
    assert audit_rows[0].new_risk == "high"
    assert audit_rows[0].reason == "escalated by legal"
    assert audit_rows[0].actor == "reviewer@example.com"


def test_override_unknown_report_is_404(client: TestClient) -> None:
    resp = client.post(
        "/contracts/no-such-report/override",
        json={"clause_id": "clause-1", "new_risk": "high", "reason": "x"},
    )
    assert resp.status_code == 404


def test_override_unknown_clause_is_404(client: TestClient) -> None:
    report = _upload(client).json()

    resp = client.post(
        f"/contracts/{report['report_id']}/override",
        json={"clause_id": "no-such-clause", "new_risk": "high", "reason": "x"},
    )
    assert resp.status_code == 404


def test_override_another_sessions_report_is_404(client: TestClient) -> None:
    """An unguessable report id is not access control - the owner is checked."""
    client.report_repo.save(  # type: ignore[attr-defined]
        ContractReviewReport(report_id="someone-elses", contract_id="c", session_id="user-2")
    )

    resp = client.post(
        "/contracts/someone-elses/override",
        json={"clause_id": "clause-1", "new_risk": "high", "reason": "x"},
    )

    assert resp.status_code == 404


def test_override_requires_auth() -> None:
    client = TestClient(create_app())
    resp = client.post(
        "/contracts/report-1/override",
        json={"clause_id": "clause-1", "new_risk": "high", "reason": "x"},
    )
    assert resp.status_code == 401
