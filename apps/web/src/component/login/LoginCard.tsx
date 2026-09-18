import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../../lib/api";
import {
  describeLoginError,
  getDevLoginUrl,
  getGoogleLoginUrl,
  isGoogleLoginAvailable,
} from "../../lib/auth";
import GoogleButton from "./GoogleButton";
import { ArrowRight, FileSearch } from "lucide-react";

/**
 * LoginCard — navy-theme glassmorphism card.
 * Navy fill, navy border, strong shadow.
 */
export default function LoginCard() {
  const [isLoading, setIsLoading] = useState(false);
  // A failed OAuth round-trip sends the browser back here as
  // /login?error=<code> rather than leaving it on a raw API error page.
  const [searchParams] = useSearchParams();
  const errorMessage = describeLoginError(searchParams.get("error"));
  // False when the app is reached over the LAN: Google rejects a private-IP
  // redirect URI before the consent screen, so the button cannot work and
  // clicking it just strands the user on a Google error page.
  const googleAvailable = isGoogleLoginAvailable();

  function handleGoogleSignIn() {
    setIsLoading(true);
    // Full-page redirect into the backend's Google OAuth flow;
    // it lands back on /auth/callback with a token once Google confirms.
    window.location.href = getGoogleLoginUrl();
  }

  function handleDevSignIn() {
    setIsLoading(true);
    window.location.href = getDevLoginUrl();
  }

  return (
    <div
      className="login-card"

    >
      <div className="mb-8">
        <span className="brand-icon mb-6"><FileSearch size={24} /></span>
        <p className="eyebrow mb-3">WELCOME TO URRISK</p>
        <h2 className="text-3xl font-semibold tracking-tight text-white">เริ่มต้นตรวจสัญญา</h2>
      </div>
      {/* Hint text */}
      <p className="mb-7 text-sm text-slate-400">
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

      {/* Google OAuth button — disabled when the API host rules it out, so the
          click can't hand the user to a Google error page with no way back. */}
      <GoogleButton
        onClick={handleGoogleSignIn}
        isLoading={isLoading}
        disabled={!googleAvailable}
      />

      {googleAvailable ? (
        /* Dev sign-in stays a quiet secondary option when Google works. */
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={handleDevSignIn}
            disabled={isLoading}
            className="secondary-button w-full justify-center"
          >
            Dev Mode Quick Sign In
          </button>
        </div>
      ) : (
        <>
          <p className="mt-4 rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-200/90">
            Google sign-in only works when the app runs on{" "}
            <code className="text-amber-100">localhost</code> or over HTTPS.
            You&apos;re on <code className="text-amber-100">{API_BASE_URL}</code>, and
            Google refuses a private-IP redirect. Use the dev sign-in below.
          </p>

          {/* Promoted to the primary action: it's the only one that can work here. */}
          <button
            type="button"
            onClick={handleDevSignIn}
            disabled={isLoading}
            className="mt-3 w-full rounded-xl border border-navy-600 bg-navy-800/60 px-6 py-3.5 text-sm font-medium text-navy-100 backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-navy-400 hover:bg-navy-700/70 hover:text-white"
          >
            Dev Mode Quick Sign In
          </button>
        </>
      )}

      {/* Sign-up link */}
      <div className="mt-8 flex items-center justify-between border-t border-navy-700/50 pt-5 text-xs text-slate-400">
        <span>บัญชี Google เดียวก็เริ่มใช้งานได้</span><ArrowRight size={16} className="text-teal-300" />
      </div>
    </div>
  );
}
