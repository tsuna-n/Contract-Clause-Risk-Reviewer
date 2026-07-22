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
