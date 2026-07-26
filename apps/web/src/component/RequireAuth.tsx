import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { fetchCurrentUser, getToken } from "../lib/auth";

/**
 * RequireAuth — route guard. Without this, protected pages like
 * /manual render regardless of login state, so deleting the token
 * has no visible effect until a guard actually checks it.
 *
 * Holding a token is not the same as having a session: JWTs expire on their
 * own and nothing tells the browser when they do. So the token only buys a
 * trip to /auth/me. Admitting anyone with a string in localStorage lets a
 * dead session into the app, where it surfaces as 401s on the first real
 * call — the user sees a broken page instead of the login screen.
 */
type Status = "checking" | "authed" | "anonymous" | "unreachable";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>(() =>
    getToken() ? "checking" : "anonymous"
  );

  useEffect(() => {
    if (status !== "checking") return;

    // The probe outlives the component if the user navigates away mid-flight;
    // setting state after that is a no-op warning, not a crash, but the flag
    // also stops a stale answer from overwriting a newer one.
    let cancelled = false;

    fetchCurrentUser().then(
      () => {
        if (!cancelled) setStatus("authed");
      },
      (err: unknown) => {
        if (cancelled) return;
        // apiFetch already discarded the token on 401. Anything else — backend
        // down, network dropped, request timed out — says nothing about
        // whether the session is still good, so don't sign the user out over
        // it; offer a retry instead.
        setStatus(
          err instanceof ApiError && !err.isUnauthorized ? "unreachable" : "anonymous"
        );
      }
    );

    return () => {
      cancelled = true;
    };
  }, [status]);

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
          onClick={() => setStatus("checking")}
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
