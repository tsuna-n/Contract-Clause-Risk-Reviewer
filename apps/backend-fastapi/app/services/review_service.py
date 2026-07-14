"""Review service: upload -> parse -> pipeline -> report."""

from __future__ import annotations

from app.agents.orchestrator import Orchestrator
from app.repositories.contract_repo import ContractRepository
from app.repositories.report_repo import ReportRepository
from app.schemas.report import ContractReviewReport


class ReviewService:
    """Coordinates parsing an upload and running the review pipeline."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        contracts: ContractRepository,
        reports: ReportRepository,
    ) -> None:
        self.orchestrator = orchestrator
        self.contracts = contracts
        self.reports = reports

    def review_upload(
        self,
        *,
        filename: str,
        data: bytes,
        session_id: str,
    ) -> ContractReviewReport:
        """Parse an uploaded file and produce a stored review report.

        TODO: dispatch to the pdf/docx parser by extension, normalize, store the
        parsed contract session-scoped, run ``orchestrator.review``, attach the
        disclaimer, persist and return the report.
        """
        raise NotImplementedError
