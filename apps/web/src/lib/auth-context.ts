import { createContext, useContext } from 'react'
import type { User } from './auth'

/**
 * The shared auth state: who is signed in, and how to stop being signed in.
 *
 * Kept apart from the provider component (component/AuthProvider) because a
 * module that exports both a component and plain values breaks Fast Refresh —
 * editing either one would remount the whole tree.
 */
export type AuthStatus = 'checking' | 'authed' | 'anonymous' | 'unreachable'

export interface AuthValue {
  status: AuthStatus
  /** The signed-in user; null until /auth/me answers, or if it never does. */
  user: User | null
  /** End the session and send the browser back to /login. */
  signOut: () => Promise<void>
  /** Re-run the session probe — after a fresh login, or a failed one. */
  refresh: () => void
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
