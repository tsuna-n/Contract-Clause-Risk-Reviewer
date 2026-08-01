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
}

/**
 * How long to wait for an evaluation run. The harness runs the full pipeline
 * (segment → classify → match → score → judge) over every item in the gold
 * set, so it's at least as slow as reviewing one contract times the set size.
 * Same reasoning as REVIEW_TIMEOUT_MS: aborting loses spent tokens and work.
 */
const EVAL_TIMEOUT_MS = 30 * 60_000;

/**
 * Run the evaluation harness against a gold set.
 *
 * Goes out with the bearer token: the backend's evaluate router declares
 * `Depends(get_current_user)`. Anonymous would 401, and apiFetch clears the
 * stored token on a 401 — so a failed run would also sign the user out.
 */
export function runEvaluation(request: EvalRequest = {}): Promise<EvalMetrics> {
  return apiFetch<EvalMetrics>("/evaluate", {
    method: "POST",
    json: request,
    timeoutMs: EVAL_TIMEOUT_MS,
  });
}
