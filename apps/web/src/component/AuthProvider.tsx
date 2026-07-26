import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ApiError } from '../lib/api'
import { fetchCurrentUser, getToken, logout, type User } from '../lib/auth'
import { AuthContext, type AuthStatus } from '../lib/auth-context'

/**
 * AuthProvider — the signed-in user, fetched once and shared.
 *
 * The session probe used to live inside RequireAuth, which threw the response
 * away after checking it was a 200. Anything that wanted to *show* who is
 * signed in (the sidebar) would have had to ask /auth/me a second time. So the
 * probe moved up here: one request answers both "may this route render?" and
 * "whose name goes in the footer?".
 *
 * Holding a token is not the same as having a session — JWTs expire on their
 * own and nothing tells the browser when they do — so the token only buys a
 * trip to /auth/me, and the answer is what the app trusts.
 */
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() =>
    getToken() ? 'checking' : 'anonymous',
  )
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    if (status !== 'checking') return

    // The probe outlives the component if the user navigates away mid-flight;
    // setting state after that is a no-op warning, not a crash, but the flag
    // also stops a stale answer from overwriting a newer one.
    let cancelled = false

    fetchCurrentUser().then(
      (me) => {
        if (cancelled) return
        setUser(me)
        setStatus('authed')
      },
      (err: unknown) => {
        if (cancelled) return
        setUser(null)
        // apiFetch already discarded the token on 401. Anything else — backend
        // down, network dropped, request timed out — says nothing about
        // whether the session is still good, so don't sign the user out over
        // it; offer a retry instead.
        setStatus(
          err instanceof ApiError && !err.isUnauthorized
            ? 'unreachable'
            : 'anonymous',
        )
      },
    )

    return () => {
      cancelled = true
    }
  }, [status])

  const refresh = useCallback(() => {
    setStatus(getToken() ? 'checking' : 'anonymous')
  }, [])

  const signOut = useCallback(async () => {
    await logout()
    setUser(null)
    setStatus('anonymous')
    // A full page load, not a router navigation: it drops every component's
    // state along with the session, so nothing rendered for the old user can
    // linger behind the login screen.
    window.location.replace('/login')
  }, [])

  return (
    <AuthContext.Provider value={{ status, user, signOut, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}
