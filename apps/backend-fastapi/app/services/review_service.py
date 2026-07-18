"""Review service: upload -> parse -> pipeline -> report."""

from __future__ import annotations

import uuid

from app.agents.orchestrator import Orchestrator
from app.core.exceptions import DocumentParseError
from app.core.retention import enforce_retention
from app.parsers.docx import parse_docx
from app.parsers.pdf import parse_pdf
from app.repositories.contract_repo import ContractRepository
from app.repositories.report_repo import ReportRepository
from app.schemas.report import ContractReviewReport

_PARSERS = {"pdf": parse_pdf, "docx": parse_docx}


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
        """Parse an uploaded file and produce a stored review report."""
        enforce_retention(session_id)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        parser = _PARSERS.get(ext)
        if parser is None:
            raise DocumentParseError(f"unsupported file type: .{ext or 'unknown'}")

        try:
            document = parser(data)
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as 422
            raise DocumentParseError(f"failed to parse {filename}: {exc}") from exc

        contract_id = uuid.uuid4().hex
        self.contracts.save(contract_id, document)
        try:
            report = self.orchestrator.review(
                document, contract_id=contract_id, session_id=session_id
            )
        finally:
            # Raw contract text isn't retained beyond producing the report.
            self.contracts.delete(contract_id)

        self.reports.save(report)
        return report
