import { apiFetch } from "./api";

// Mirrors `EvalMetrics` / `PerTypeMetrics` in app/schemas.py exactly.
export interface PerTypeMetrics {
  clause_type: string;
  support: number;
  accuracy: number;
}

export interface EvalMetrics {
  segmentation_f1: number;
  classification_accuracy: number;
  risk_accuracy: number;
  citation_validity: number;
  per_type: PerTypeMetrics[];
}

export interface EvalRequest {
  gold_set_path?: string;
  limit?: number;
  order?: "file" | "shortest";
}

export interface EvalJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  total_contracts: number;
  completed_contracts: number;
  contract_id: string | null;
  total_clauses: number;
  completed_clauses: number;
  elapsed_seconds: number;
  metrics: EvalMetrics | null;
  error: string | null;
}

export function startEvaluation(request: EvalRequest): Promise<EvalJob> {
  return apiFetch<EvalJob>("/evaluate/jobs", { method: "POST", json: request });
}

export function getEvaluation(jobId: string, signal?: AbortSignal): Promise<EvalJob> {
  return apiFetch<EvalJob>(`/evaluate/jobs/${encodeURIComponent(jobId)}`, { signal });
}

// Retained for callers that explicitly need the blocking endpoint.
export function runEvaluation(request: EvalRequest = {}): Promise<EvalMetrics> {
  return apiFetch<EvalMetrics>("/evaluate", {
    method: "POST", json: request, timeoutMs: 30 * 60_000,
  });
}
