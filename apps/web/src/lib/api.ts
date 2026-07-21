const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export { API_BASE_URL };

/**
 * ApiError — a failed backend call, normalized.
 *
 * The backend speaks two error dialects: domain errors from
 * `register_exception_handlers` ({error, message}) and FastAPI's own
 * validation/auth errors ({detail}). Callers shouldn't have to care, so
 * both collapse into `code` + `message` here.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** True when the session is missing/expired and the user must sign in again. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

const TOKEN_KEY = "access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function describeDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors arrive as a list of {loc, msg, type}.
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null
      )
      .filter((part): part is string => Boolean(part));
    if (parts.length) return parts.join("; ");
  }
  return null;
}

async function toApiError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let message = res.statusText || `Request failed (${res.status})`;

  try {
    const body = await res.json();
    if (body && typeof body === "object") {
      const domainMessage = typeof body.message === "string" ? body.message : null;
      const detailMessage = describeDetail(body.detail);
      if (typeof body.error === "string") code = body.error;
      if (domainMessage ?? detailMessage) message = (domainMessage ?? detailMessage)!;
    }
  } catch {
    // Non-JSON body (proxy error page, empty 502). Keep the status-based message.
  }

  return new ApiError(res.status, code, message);
}

interface ApiFetchOptions {
  method?: string;
  body?: BodyInit;
  /** Send the stored bearer token. Defaults to true. */
  auth?: boolean;
  signal?: AbortSignal;
}

/**
 * apiFetch — one call against the backend, with auth and error handling applied.
 *
 * A 401 clears the stored token so the route guards send the user back to
 * /login instead of looping on a dead session.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;

  const headers: Record<string, string> = {};
  if (auth) {
    const token = getToken();
    if (!token) throw new ApiError(401, "not_authenticated", "Not signed in");
    headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { method, body, headers, signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "network_error",
      `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`
    );
  }

  if (!res.ok) {
    const apiError = await toApiError(res);
    if (apiError.isUnauthorized) clearToken();
    throw apiError;
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
