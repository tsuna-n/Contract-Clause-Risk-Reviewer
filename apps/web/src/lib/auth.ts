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
