// Shared types for contract components

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface Clause {
  id: string;
  title: string;
  text: string;
  riskLevel: RiskLevel;
  excerpt: string;
  playbookMatch: string;
  aiRationale: string;
  suggestedFallback: string;
  citations: string[];
}

export interface ContractMetadata {
  contractType: string;
  contractTitle: string;
  contractingParties: string;
  contractExecutionDate: string;
  effectiveDate: string;
  expirationDate: string;
  contractValue?: string;
  contractTerm: string;
}

