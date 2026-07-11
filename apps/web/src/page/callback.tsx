import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { consumeTokenFromUrl, getToken } from "../lib/auth";

/**
 * AuthCallbackPage — landing target for the backend's Google OAuth
 * redirect (/auth/callback?token=...). Stores the token, then forwards
 * the user into the app (or back to /login if something went wrong).
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    consumeTokenFromUrl();
    navigate(getToken() ? "/manual" : "/login", { replace: true });
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-black text-sm text-zinc-400">
      Signing you in…
    </div>
  );
}
