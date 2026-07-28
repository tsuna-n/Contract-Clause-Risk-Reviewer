import type { ContractReport } from "../component/contract/types";

/**
 * Report export — JSON and CSV, built entirely in the browser.
 *
 * There is no export endpoint on the backend, and this needs none: by the time
 * a report is on screen the whole `ContractReport` is already in memory, so
 * downloading it is a serialization problem rather than an API one. The one
 * thing the exports don't carry is `span.start/end` — character offsets into
 * the normalized document, which the mapper drops before the UI ever sees a
 * clause and which mean nothing outside the pipeline.
 */

/** `2026-07-28` — the date part of an ISO timestamp, for filenames. */
function isoDate(iso: string): string {
  const parsed = new Date(iso);
  const date = Number.isNaN(parsed.valueOf()) ? new Date() : parsed;
  return date.toISOString().slice(0, 10);
}

/**
 * A filename that is safe on every platform and still recognizable.
 *
 * The contract's own name is the useful part, so it leads — minus its
 * extension, which would otherwise leave "contract.docx-risk-report.csv".
 */
export function exportFilename(report: ContractReport, extension: string): string {
  const base =
    report.filename.replace(/\.(pdf|docx)$/i, "").trim() || report.contractId;
  // Windows forbids \ / : * ? " < > | in filenames; spaces collapse into the
  // same hyphen so the result stays one word at a shell prompt.
  const safe = base.replace(/[\\/:*?"<>| -]+/g, "-").slice(0, 80);
  return `${safe}-risk-report-${isoDate(report.createdAt)}.${extension}`;
}

/** The report as JSON — the same shape the UI renders, minus internal offsets. */
export function reportToJson(report: ContractReport): string {
  return JSON.stringify(
    {
      report_id: report.reportId,
      contract_id: report.contractId,
      filename: report.filename,
      created_at: report.createdAt,
      exported_at: new Date().toISOString(),
      overall_risk: report.overallRisk,
      summary: report.summary,
      disclaimer: report.disclaimer,
      clauses: report.clauses.map((clause, index) => ({
        index: index + 1,
        id: clause.id,
        title: clause.title,
        clause_type: clause.clauseType,
        risk_level: clause.riskLevel,
        // The judge's grounding verdict. Named for what it means rather than
        // the DTO's `verified`, which reads like "a human checked this".
        grounded_in_playbook: clause.verified,
        page: clause.page,
        rationale: clause.rationale,
        suggested_fallback: clause.suggestedFallback,
        citations: clause.citations.map((citation) => ({
          id: citation.id,
          playbook_position_id: citation.playbookPositionId,
          excerpt: citation.excerpt,
        })),
        text: clause.text,
      })),
    },
    null,
    2
  );
}

/**
 * Quote one CSV field.
 *
 * The leading-quote guard is not cosmetic: a cell starting with `=`, `+`, `-`
 * or `@` is a formula to Excel and Sheets, and this file is full of contract
 * text nobody vetted. Prefixing an apostrophe makes the spreadsheet treat it
 * as text — the standard mitigation for CSV injection.
 */
function csvCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '""';
  const text = String(value);
  const guarded = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${guarded.replace(/"/g, '""')}"`;
}

const CSV_HEADERS = [
  "#",
  "clause_id",
  "title",
  "clause_type",
  "risk_level",
  "grounded_in_playbook",
  "page",
  "rationale",
  "suggested_fallback",
  "citations",
  "clause_text",
] as const;

/**
 * One row per clause — the shape a reviewer can sort and filter in a
 * spreadsheet, which is the whole reason CSV is offered next to JSON.
 */
export function reportToCsv(report: ContractReport): string {
  const rows = report.clauses.map((clause, index) =>
    [
      csvCell(index + 1),
      csvCell(clause.id),
      csvCell(clause.title),
      csvCell(clause.clauseType),
      csvCell(clause.riskLevel),
      csvCell(clause.verified ? "yes" : "no"),
      csvCell(clause.page),
      csvCell(clause.rationale),
      csvCell(clause.suggestedFallback),
      // Flattened rather than split across columns: the count varies per
      // clause, and a rectangle can't hold a ragged list.
      csvCell(
        clause.citations
          .map((citation) => `${citation.playbookPositionId}: ${citation.excerpt}`)
          .join("\n\n")
      ),
      csvCell(clause.text),
    ].join(",")
  );

  return [CSV_HEADERS.map(csvCell).join(","), ...rows].join("\r\n");
}

/** Hand a generated file to the browser's downloader. */
function download(filename: string, mimeType: string, content: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoking synchronously can cancel the download in some browsers; a task
  // later is after the click has been handled.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadReportJson(report: ContractReport): void {
  download(
    exportFilename(report, "json"),
    "application/json;charset=utf-8",
    reportToJson(report)
  );
}

export function downloadReportCsv(report: ContractReport): void {
  // The BOM is what makes Excel read the file as UTF-8. Without it, Thai text
  // and typographic quotes open as mojibake on a default Windows install.
  // Written as an escape rather than the literal character, which is
  // zero-width and so invisible in a diff.
  download(
    exportFilename(report, "csv"),
    "text/csv;charset=utf-8",
    `\uFEFF${reportToCsv(report)}`
  );
}
