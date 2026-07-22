import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { describeLoginError, getGoogleLoginUrl } from "../../lib/auth";
import GoogleButton from "./GoogleButton";
import SignUpLink from "./SignUpLink";

/**
 * LoginCard — black-theme glassmorphism card.
 * Nearly-black fill, white/8 border, strong shadow.
 */
export default function LoginCard() {
  const [isLoading, setIsLoading] = useState(false);
  // A failed OAuth round-trip sends the browser back here as
  // /login?error=<code> rather than leaving it on a raw API error page.
  const [searchParams] = useSearchParams();
  const errorMessage = describeLoginError(searchParams.get("error"));

  function handleGoogleSignIn() {
    setIsLoading(true);
    // Full-page redirect into the backend's Google OAuth flow;
    // it lands back on /auth/callback with a token once Google confirms.
    window.location.href = getGoogleLoginUrl();
  }

  return (
    <div
      className="w-full rounded-2xl border border-white/8 bg-white/[0.03] p-7 backdrop-blur-xl"
      style={{
        boxShadow:
          "0 8px 48px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.04)",
      }}
    >
      {/* Hint text */}
      <p className="mb-5 text-center text-sm text-zinc-500">
        Sign in to your workspace
      </p>

      {/* Why the last sign-in attempt didn't go through */}
      {errorMessage && (
        <p
          role="alert"
          className="mb-5 rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-center text-sm text-red-300"
        >
          {errorMessage}
        </p>
      )}

      {/* Google OAuth button */}
      <GoogleButton onClick={handleGoogleSignIn} isLoading={isLoading} />

      {/* Sign-up link */}
      <div className="mt-5">
        <SignUpLink />
      </div>
    </div>
  );
}
