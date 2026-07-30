import { apiFetch } from "./api";
import type {
  ClauseView,
  ContractMetadataView,
  ContractReport,
  ReportSummary,
  RiskLevel,
} from "../component/contract/types";

// ── Backend DTOs ───────────────────────────────────────────────────────────────
// These mirror apps/backend-fastapi/app/schemas.py exactly, snake_case and
// all. Everything the UI actually renders goes through the mappers below, so
// the shape only has to be right in this one file.

/** Matches `RiskLevel` in app/schemas.py — lowercase, no CRITICAL. */
export type BackendRiskLevel = "low" | "medium" | "high" | "unknown";

/** Matches `ClauseType` in app/schemas.py. */
export type BackendClauseType =
  | "confidentiality"
  | "indemnification"
  | "limitation_of_liability"
  | "termination"
  | "governing_law"
  | "intellectual_property"
  | "payment_terms"
  | "warranty"
  | "non_compete"
  | "data_protection"
  | "force_majeure"
  | "other";

interface BackendSpan {
  start: number;
  end: number;
  page: number | null;
}

interface BackendClause {
  id: string;
  text: string;
  span: BackendSpan;
  clause_type: BackendClauseType;
  heading: string | null;
}

interface BackendCitation {
  citation_id: string;
  playbook_position_id: string;
  excerpt: string;
}

interface BackendClauseReview {
  clause: BackendClause;
  risk_level: BackendRiskLevel;
  rationale: string;
  citations: BackendCitation[];
  suggested_fallback: string | null;
  /** The judge's grounding verdict — the pipeline checking its own work. */
  verified: boolean;
  /** A person's sign-off — set by `POST /contracts/{id}/accept`. */
  accepted: boolean;
  accepted_by: string | null;
  accepted_at: string | null;
}

interface BackendRiskSummary {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

/** Matches `ContractMetadata` in app/schemas.py — verbatim quotes, all optional. */
interface BackendContractMetadata {
  parties: string[];
  agreement_date: string | null;
  effective_date: string | null;
  expiration_date: string | null;
  contract_value: string | null;
  governing_law: string | null;
}

// `session_id` is intentionally absent: the backend keeps it on the report for
// session-scoped purging but strips it from responses, so declaring it here
// would promise a field that never arrives.
export interface BackendContractReviewReport {
  report_id: string;
  contract_id: string;
  filename: string;
  created_at: string;
  overall_risk: BackendRiskLevel;
  summary: BackendRiskSummary;
  reviews: BackendClauseReview[];
  metadata: BackendContractMetadata;
  disclaimer: string;
}

/** Matches `ReportSummary` in app/schemas.py — a history row, no clause detail. */
interface BackendReportSummary {
  report_id: string;
  contract_id: string;
  filename: string;
  created_at: string;
  overall_risk: BackendRiskLevel;
  summary: BackendRiskSummary;
  clause_count: number;
}

// ── Mapping: backend DTO -> view model ─────────────────────────────────────────

export function toRiskLevel(risk: BackendRiskLevel): RiskLevel {
  return risk.toUpperCase() as RiskLevel;
}

export function toBackendRiskLevel(risk: RiskLevel): BackendRiskLevel {
  return risk.toLowerCase() as BackendRiskLevel;
}

/** "limitation_of_liability" -> "Limitation Of Liability" */
function humanizeClauseType(clauseType: BackendClauseType): string {
  return clauseType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Longest `heading` still usable as a title.
 *
 * The segmenter often sets `heading` to the entire clause, so a length check
 * is what separates a real heading ("2. Limitation of Liability") from a
 * paragraph masquerading as one.
 */
const HEADING_MAX_CHARS = 80;

/**
 * The numbering a clause opens with: "2. ", "(3) ", "Section 4. ", "ข้อ 5. ",
 * "๑. " — mirroring the headings `app/parsers.py` recognizes.
 *
 * Requires whitespace after the number so that a figure inside a sentence
 * ("1.5% per month") isn't mistaken for a clause number and chopped off.
 */
const CLAUSE_NUMBERING =
  /^(?:ข้อที่|ข้อ|Article|Section|Clause)?\s*\(?[\d๐-๙]+(?:\.[\d๐-๙]+)*[.)]?\s+/i;

/**
 * Pull a title out of the clause's own opening, e.g.
 * "2. Limitation of Liability. Supplier shall…" -> "Limitation of Liability".
 *
 * Only used when the classifier returned OTHER, where the humanized type
 * ("Other") tells the reviewer nothing.
 */
function leadingLabel(text: string): string | null {
  const withoutNumbering = text.trim().replace(CLAUSE_NUMBERING, "");
  const label = withoutNumbering.split(".")[0]?.trim();
  if (!label || label.length < 3 || label.length > HEADING_MAX_CHARS) return null;
  if (!/[a-zA-Z฀-๿]/.test(label)) return null;
  return label;
}

/** A short, human-readable title for a clause. */
function toTitle(clause: BackendClause): string {
  const heading = clause.heading?.trim();
  if (heading && heading.length <= HEADING_MAX_CHARS && heading !== clause.text.trim()) {
    // The lists that render this already number their rows, so a heading that
    // carries its own number reads as "1. ข้อ 1. การรักษาความลับ". Drop the
    // clause's copy and keep the list's — unless stripping leaves nothing,
    // which means the number *was* the heading.
    return heading.replace(CLAUSE_NUMBERING, "").trim() || heading;
  }
  if (clause.clause_type === "other") {
    const derived = leadingLabel(clause.text);
    if (derived) return derived;
  }
  return humanizeClauseType(clause.clause_type);
}

const EXCERPT_MAX_CHARS = 240;

/** The clause text, trimmed to a quotable length for the analysis panel. */
function toExcerpt(text: string): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  if (collapsed.length <= EXCERPT_MAX_CHARS) return collapsed;
  return `${collapsed.slice(0, EXCERPT_MAX_CHARS).trimEnd()}…`;
}

function toClauseView(review: BackendClauseReview): ClauseView {
  const { clause } = review;
  return {
    id: clause.id,
    title: toTitle(clause),
    clauseType: clause.clause_type,
    text: clause.text,
    excerpt: toExcerpt(clause.text),
    riskLevel: toRiskLevel(review.risk_level),
    rationale: review.rationale,
    suggestedFallback: review.suggested_fallback,
    citations: review.citations.map((citation) => ({
      id: citation.citation_id,
      playbookPositionId: citation.playbook_position_id,
      excerpt: citation.excerpt,
    })),
    verified: review.verified,
    accepted: review.accepted,
    acceptedBy: review.accepted_by,
    acceptedAt: review.accepted_at,
    page: clause.span.page,
  };
}

/**
 * Reports stored before metadata extraction existed come back without the
 * field, so it is treated as optional here rather than trusted to be present.
 */
function toContractMetadata(
  metadata: BackendContractMetadata | undefined
): ContractMetadataView {
  return {
    parties: metadata?.parties ?? [],
    agreementDate: metadata?.agreement_date ?? null,
    effectiveDate: metadata?.effective_date ?? null,
    expirationDate: metadata?.expiration_date ?? null,
    contractValue: metadata?.contract_value ?? null,
    governingLaw: metadata?.governing_law ?? null,
  };
}

export function toContractReport(report: BackendContractReviewReport): ContractReport {
  return {
    reportId: report.report_id,
    contractId: report.contract_id,
    filename: report.filename,
    createdAt: report.created_at,
    overallRisk: toRiskLevel(report.overall_risk),
    summary: report.summary,
    metadata: toContractMetadata(report.metadata),
    disclaimer: report.disclaimer,
    clauses: report.reviews.map(toClauseView),
  };
}

function toReportSummary(row: BackendReportSummary): ReportSummary {
  return {
    reportId: row.report_id,
    contractId: row.contract_id,
    filename: row.filename,
    createdAt: row.created_at,
    overallRisk: toRiskLevel(row.overall_risk),
    summary: row.summary,
    clauseCount: row.clause_count,
  };
}

// ── Calls ──────────────────────────────────────────────────────────────────────

/** Extensions the backend has a parser for (see `PARSERS` in app/parsers.py). */
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.join(",");

export function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

/**
 * How long to wait for a full review.
 *
 * The request stays open for the whole pipeline, which runs serially and makes
 * roughly four Gemini calls per clause (classify, match, score, judge).
 * Measured against the real API, one structured call averages ~15s, so a
 * 20-clause contract lands near 20 minutes. This is set above that worst case
 * on purpose: aborting a healthy review loses all the work and all the tokens
 * already spent on it, which is far worse than waiting. It still bounds a
 * genuinely wedged request instead of spinning forever.
 *
 * If this ever needs to come down, the fix is a faster pipeline (run clauses
 * concurrently, or lower the thinking effort on the cheap classify step) —
 * not a shorter deadline.
 */
export const REVIEW_TIMEOUT_MS = 25 * 60_000;

/** Upload a contract and run the review pipeline. */
export async function reviewContract(
  file: File,
  signal?: AbortSignal
): Promise<ContractReport> {
  const formData = new FormData();
  formData.append("file", file);

  const report = await apiFetch<BackendContractReviewReport>("/contracts/review", {
    method: "POST",
    body: formData,
    signal,
    timeoutMs: REVIEW_TIMEOUT_MS,
  });
  return toContractReport(report);
}

/**
 * This user's past reviews, newest first.
 *
 * Reports are stored in Postgres and kept until their owner deletes them, so
 * this is the full archive rather than a recent-items list.
 */
export async function fetchReportHistory(signal?: AbortSignal): Promise<ReportSummary[]> {
  const rows = await apiFetch<BackendReportSummary[]>("/contracts", { signal });
  return rows.map(toReportSummary);
}

/** Load one stored report in full, by id. */
export async function fetchReport(
  reportId: string,
  signal?: AbortSignal
): Promise<ContractReport> {
  const report = await apiFetch<BackendContractReviewReport>(
    `/contracts/${encodeURIComponent(reportId)}`,
    { signal }
  );
  return toContractReport(report);
}

export interface OverrideRequest {
  reportId: string;
  clauseId: string;
  newRisk: RiskLevel;
  reason: string;
}

/**
 * Longest `reason` the backend will accept — `OverrideRequest.reason` in
 * app/schemas.py. Mirrored here so the textarea can stop the user at the limit
 * instead of letting them write past it and lose the text to a 422.
 */
export const OVERRIDE_REASON_MAX_CHARS = 1000;

/**
 * Apply a human override to one clause's risk level.
 *
 * Sent as a JSON body: `reason` is text a reviewer typed, and it's the audit
 * trail — a query string would copy it into access logs and browser history.
 * Returns the whole updated report, which becomes the page's new state.
 */
export async function overrideClause({
  reportId,
  clauseId,
  newRisk,
  reason,
}: OverrideRequest): Promise<ContractReport> {
  const report = await apiFetch<BackendContractReviewReport>(
    `/contracts/${encodeURIComponent(reportId)}/override`,
    {
      method: "POST",
      json: {
        clause_id: clauseId,
        new_risk: toBackendRiskLevel(newRisk),
        reason,
      },
    }
  );
  return toContractReport(report);
}

export interface AcceptRequest {
  reportId: string;
  clauseId: string;
  /** `false` withdraws a sign-off made earlier. */
  accepted: boolean;
  note?: string;
}

/**
 * Sign off on one clause's assessment, or take the sign-off back.
 *
 * Risk levels don't move — accepting says the reviewer agrees with what the
 * pipeline found. Like override, the response is the whole updated report and
 * replaces page state, so the ✓ a reviewer sees is the server's copy rather
 * than an optimistic guess at it.
 */
export async function acceptClause({
  reportId,
  clauseId,
  accepted,
  note,
}: AcceptRequest): Promise<ContractReport> {
  const report = await apiFetch<BackendContractReviewReport>(
    `/contracts/${encodeURIComponent(reportId)}/accept`,
    {
      method: "POST",
      json: { clause_id: clauseId, accepted, ...(note ? { note } : {}) },
    }
  );
  return toContractReport(report);
}

/** Delete a stored review report from DB. */
export async function deleteReport(reportId: string): Promise<void> {
  await apiFetch<void>(`/contracts/${encodeURIComponent(reportId)}`, {
    method: "DELETE",
  });
}

