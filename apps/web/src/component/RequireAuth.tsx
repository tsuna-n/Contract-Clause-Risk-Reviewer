import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth-context";

/**
 * RequireAuth — route guard. Without this, protected pages like
 * /manual render regardless of login state, so deleting the token
 * has no visible effect until a guard actually checks it.
 *
 * The session probe itself lives in AuthProvider (see lib/auth-context), which
 * shares one /auth/me answer between this guard and everything that displays
 * the user. This component only decides what to do with that answer.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status, refresh } = useAuth();

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black text-sm text-zinc-400">
        Checking your session…
      </div>
    );
  }

  if (status === "unreachable") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-black px-4 text-center">
        <p className="text-sm text-zinc-400">
          Couldn't reach the server to confirm your session. You're still signed
          in — this is a connection problem, not a login problem.
        </p>
        <button
          type="button"
          onClick={refresh}
          className="rounded-xl border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/20 hover:bg-white/10 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }

  if (status === "anonymous") return <Navigate to="/login" replace />;
  return children;
}
