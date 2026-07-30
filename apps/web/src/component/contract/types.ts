// View-model types for the contract components.
//
// These are the UI's shape, not the wire shape — `lib/contracts.ts` owns the
// translation from the backend's snake_case DTOs. Risk levels mirror the
// backend taxonomy (app/schemas.py): there is no CRITICAL, and
// UNKNOWN is a real outcome the pipeline returns when a clause fails review.

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";

/** Risk levels a reviewer may override *to*, worst first. */
export const OVERRIDE_RISK_LEVELS: RiskLevel[] = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"];

export interface Citation {
  id: string;
  playbookPositionId: string;
  excerpt: string;
}

export interface ClauseView {
  id: string;
  /** Heading from the document, or the classified clause type as a fallback. */
  title: string;
  clauseType: string;
  text: string;
  /** `text`, trimmed for quoting in the analysis panel. */
  excerpt: string;
  riskLevel: RiskLevel;
  rationale: string;
  suggestedFallback: string | null;
  citations: Citation[];
  /** The judge confirmed the rationale is grounded in the cited playbook text. */
  verified: boolean;
  /**
   * A reviewer signed off on this assessment.
   *
   * Stored on the report by `POST /contracts/{id}/accept`, not kept in the
   * page: review progress that a refresh erased was worse than no progress at
   * all, because it looked like work had been lost rather than never saved.
   */
  accepted: boolean;
  acceptedBy: string | null;
  acceptedAt: string | null;
  page: number | null;
}

export interface RiskSummary {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

/**
 * Contract-level facts the pipeline read out of the document.
 *
 * Every value is verbatim text from the file — the backend discards anything
 * it can't find there word-for-word — so these are quotes, not conclusions.
 * Dates stay as the document wrote them ("the 3rd day of March, 2019"); don't
 * reformat them here, that would undo the point of quoting.
 *
 * Any field can be absent, and an all-empty metadata block is normal: the
 * document simply didn't say.
 */
export interface ContractMetadataView {
  parties: string[];
  agreementDate: string | null;
  effectiveDate: string | null;
  expirationDate: string | null;
  contractValue: string | null;
  governingLaw: string | null;
}

export interface ContractReport {
  reportId: string;
  contractId: string;
  /** The uploaded file's name — what the report is called in the UI. */
  filename: string;
  createdAt: string;
  overallRisk: RiskLevel;
  summary: RiskSummary;
  metadata: ContractMetadataView;
  disclaimer: string;
  clauses: ClauseView[];
}

/**
 * One row of review history: a report without its clause reviews.
 *
 * The sidebar renders every past review at once and shows none of the clause
 * detail, so the backend sends these instead of whole reports. Opening one
 * fetches the full `ContractReport`.
 */
export interface ReportSummary {
  reportId: string;
  contractId: string;
  filename: string;
  createdAt: string;
  overallRisk: RiskLevel;
  summary: RiskSummary;
  clauseCount: number;
}
