import { apiFetch } from "./api";
import type { ClauseView, ContractReport, RiskLevel } from "../component/contract/types";

// ── Backend DTOs ───────────────────────────────────────────────────────────────
// These mirror apps/backend-fastapi/app/schemas/*.py exactly, snake_case and
// all. Everything the UI actually renders goes through the mappers below, so
// the shape only has to be right in this one file.

/** Matches `RiskLevel` in app/schemas/taxonomy.py — lowercase, no CRITICAL. */
export type BackendRiskLevel = "low" | "medium" | "high" | "unknown";

/** Matches `ClauseType` in app/schemas/taxonomy.py. */
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
  verified: boolean;
}

interface BackendRiskSummary {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

export interface BackendContractReviewReport {
  report_id: string;
  contract_id: string;
  session_id: string;
  created_at: string;
  overall_risk: BackendRiskLevel;
  summary: BackendRiskSummary;
  reviews: BackendClauseReview[];
  disclaimer: string;
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
 * Pull a title out of the clause's own opening, e.g.
 * "2. Limitation of Liability. Supplier shall…" -> "Limitation of Liability".
 *
 * Only used when the classifier returned OTHER, where the humanized type
 * ("Other") tells the reviewer nothing.
 */
function leadingLabel(text: string): string | null {
  // Strips "2. ", "(3) ", "Section 4. " and the Thai "ข้อ 5. " so the label is
  // the clause's subject rather than its number.
  const withoutNumbering = text
    .trim()
    .replace(/^(?:ข้อที่|ข้อ|Article|Section|Clause)?\s*\(?\d+[.)]\s*/i, "");
  const label = withoutNumbering.split(".")[0]?.trim();
  if (!label || label.length < 3 || label.length > HEADING_MAX_CHARS) return null;
  if (!/[a-zA-Z฀-๿]/.test(label)) return null;
  return label;
}

/** A short, human-readable title for a clause. */
function toTitle(clause: BackendClause): string {
  const heading = clause.heading?.trim();
  if (heading && heading.length <= HEADING_MAX_CHARS && heading !== clause.text.trim()) {
    return heading;
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
    page: clause.span.page,
  };
}

export function toContractReport(report: BackendContractReviewReport): ContractReport {
  return {
    reportId: report.report_id,
    contractId: report.contract_id,
    createdAt: report.created_at,
    overallRisk: toRiskLevel(report.overall_risk),
    summary: report.summary,
    disclaimer: report.disclaimer,
    clauses: report.reviews.map(toClauseView),
  };
}

// ── Calls ──────────────────────────────────────────────────────────────────────

/** Extensions the backend has a parser for (see `_PARSERS` in review_service.py). */
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx"] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.join(",");

export function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

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
  });
  return toContractReport(report);
}

export interface OverrideRequest {
  reportId: string;
  clauseId: string;
  newRisk: RiskLevel;
  reason: string;
}

/**
 * Apply a human override to one clause's risk level.
 *
 * The endpoint takes its arguments as query params (they're plain scalars on
 * the FastAPI handler, not a request body) and returns the whole updated
 * report, which becomes the page's new state.
 */
export async function overrideClause({
  reportId,
  clauseId,
  newRisk,
  reason,
}: OverrideRequest): Promise<ContractReport> {
  const params = new URLSearchParams({
    clause_id: clauseId,
    new_risk: toBackendRiskLevel(newRisk),
    reason,
  });

  const report = await apiFetch<BackendContractReviewReport>(
    `/contracts/${encodeURIComponent(reportId)}/override?${params}`,
    { method: "POST" }
  );
  return toContractReport(report);
}
