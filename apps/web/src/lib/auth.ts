import { API_BASE_URL, apiFetch, clearToken, getToken, setToken } from './api'

export { clearToken, getToken }

export interface User {
  id: string
  email: string
  name: string | null
  picture: string | null
}

export function getGoogleLoginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`
}

// The backend sends failed sign-ins back to /login?error=<code>. Codes come
// straight from Google (or from authlib), so translate the ones a user can
// actually act on and fall back to something honest for the rest.
const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'Sign-in was cancelled. Approve access with Google to continue.',
  mismatching_state:
    'Your sign-in session expired before Google replied. Please try again.',
  missing_email:
    "Google didn't share an email address for that account, so we can't sign you in.",
  admin_policy_enforced:
    'Your Google Workspace administrator has blocked access to this app.',
  org_internal:
    'That account is outside the organization allowed to use this app.',
}

export function describeLoginError(code: string | null): string | null {
  if (!code) return null
  return (
    LOGIN_ERROR_MESSAGES[code] ??
    `Sign-in with Google failed (${code}). Please try again.`
  )
}

// After Google login, the backend redirects to /auth/callback?token=...
// Pick up that token (if present) and clean the URL.
export function consumeTokenFromUrl(): void {
  if (window.location.pathname !== '/auth/callback') return

  const token = new URLSearchParams(window.location.search).get('token')
  if (token) setToken(token)

  window.history.replaceState({}, '', '/')
}

export function fetchCurrentUser(): Promise<User> {
  // apiFetch clears the stored token on 401, so an expired session lands the
  // user back at /login via the route guard instead of retrying forever.
  return apiFetch<User>('/auth/me')
}

/**
 * A logout must not hang on a slow backend. The local clear happens either
 * way, so a short ceiling only trades away the server-side cookie expiry —
 * and waiting the default 30s with the token still in localStorage is worse.
 */
const LOGOUT_TIMEOUT_MS = 5_000

/**
 * Expire every cookie this origin can see.
 *
 * Only reaches cookies set by the frontend origin and readable from JS:
 * HttpOnly cookies, and anything the API set on its own origin, are invisible
 * here — those are the backend's to delete, which is why /auth/logout does it
 * server-side. Both halves are needed; neither covers the other.
 */
function clearBrowserCookies(): void {
  for (const entry of document.cookie.split(';')) {
    const name = entry.split('=')[0]?.trim()
    if (!name) continue
    // A cookie is identified by name+path, so a delete that doesn't name the
    // right path silently misses. Cover the current path and its parents.
    const segments = window.location.pathname.split('/')
    const paths = segments.map((_, i) => segments.slice(0, i + 1).join('/') || '/')
    for (const path of new Set(['/', ...paths])) {
      document.cookie = `${name}=; path=${path}; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`
    }
  }
}

/**
 * Sign out: end the session on the server, then wipe every trace of it here.
 *
 * Awaited, unlike a fire-and-forget POST, because the server ends the session
 * by *replying* with an expired session cookie — navigating away mid-flight
 * aborts the request and leaves that cookie in the browser. The local clear
 * runs in `finally` so a backend that is down or slow can't strand a signed-in
 * looking UI.
 */
export async function logout(): Promise<void> {
  try {
    await apiFetch<{ message: string }>('/auth/logout', {
      method: 'POST',
      // Without this the browser neither sends the session cookie nor stores
      // the expiry the response carries: the API is a different origin.
      credentials: 'include',
      timeoutMs: LOGOUT_TIMEOUT_MS,
    })
  } catch {
    // Nothing to recover — the session is over on this device either way.
  } finally {
    clearToken()
    sessionStorage.clear()
    clearBrowserCookies()
  }
}
