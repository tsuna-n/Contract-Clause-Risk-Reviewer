import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { consumeTokenFromUrl, getToken } from "../lib/auth";
import { useAuth } from "../lib/auth-context";

/**
 * AuthCallbackPage — landing target for the backend's Google OAuth
 * redirect (/auth/callback?token=...). Stores the token, then forwards
 * the user into the app (or back to /login if something went wrong).
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const { refresh } = useAuth();

  useEffect(() => {
    consumeTokenFromUrl();
    // AuthProvider decided "anonymous" when this page loaded — there was no
    // token yet. Without this the guard on the next route would bounce a user
    // who *just* signed in straight back to /login.
    refresh();
    navigate(getToken() ? "/layout/chat-layout" : "/login", { replace: true });
  }, [navigate, refresh]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-black text-sm text-zinc-400">
      Signing you in…
    </div>
  );
}
