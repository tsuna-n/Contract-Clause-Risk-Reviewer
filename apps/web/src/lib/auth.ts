const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'access_token'

export interface User {
  id: string
  email: string
  name: string | null
  picture: string | null
}

export function getGoogleLoginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// After Google login, the backend redirects to /auth/callback?token=...
// Pick up that token (if present) and clean the URL.
export function consumeTokenFromUrl(): void {
  if (window.location.pathname !== '/auth/callback') return

  const token = new URLSearchParams(window.location.search).get('token')
  if (token) localStorage.setItem(TOKEN_KEY, token)

  window.history.replaceState({}, '', '/')
}

export async function fetchCurrentUser(): Promise<User> {
  const token = getToken()
  if (!token) throw new Error('Not signed in')

  const res = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })

  if (!res.ok) {
    clearToken()
    throw new Error('Session expired')
  }

  return res.json()
}
