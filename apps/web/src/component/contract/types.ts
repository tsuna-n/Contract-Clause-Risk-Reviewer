// View-model types for the contract components.
//
// These are the UI's shape, not the wire shape — `lib/contracts.ts` owns the
// translation from the backend's snake_case DTOs. Risk levels mirror the
// backend taxonomy (app/schemas/taxonomy.py): there is no CRITICAL, and
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
  page: number | null;
}

export interface RiskSummary {
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

export interface ContractReport {
  reportId: string;
  contractId: string;
  createdAt: string;
  overallRisk: RiskLevel;
  summary: RiskSummary;
  disclaimer: string;
  clauses: ClauseView[];
}
