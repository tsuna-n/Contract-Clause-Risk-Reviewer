import { apiFetch } from "./api";

// Mirrors the small ad-hoc JSON the health/root routes return.
export interface RootStatus {
  service: string;
  status: string;
}

export interface HealthStatus {
  status: string;
  database?: string;
}

const HEALTH_TIMEOUT_MS = 5_000;

/** Root service ping — `GET /`. */
export function checkRoot(): Promise<RootStatus> {
  return apiFetch<RootStatus>("/", { auth: false, timeoutMs: HEALTH_TIMEOUT_MS });
}

/** Liveness probe — `GET /health`. */
export function checkHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health", { auth: false, timeoutMs: HEALTH_TIMEOUT_MS });
}

/** DB readiness probe — `GET /health/db` (503 if the DB is down). */
export function checkHealthDb(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health/db", { auth: false, timeoutMs: HEALTH_TIMEOUT_MS });
}
