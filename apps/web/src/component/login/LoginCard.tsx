import { useState } from "react";
import GoogleButton from "./GoogleButton";
import SignUpLink from "./SignUpLink";

/**
 * LoginCard — black-theme glassmorphism card.
 * Nearly-black fill, white/8 border, strong shadow.
 */
export default function LoginCard() {
  const [isLoading, setIsLoading] = useState(false);

  async function handleGoogleSignIn() {
    setIsLoading(true);
    try {
      // TODO: integrate real OAuth / auth provider
      await new Promise((res) => setTimeout(res, 1200));
    } finally {
      setIsLoading(false);
    }
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

      {/* Google OAuth button */}
      <GoogleButton onClick={handleGoogleSignIn} isLoading={isLoading} />

      {/* Sign-up link */}
      <div className="mt-5">
        <SignUpLink />
      </div>
    </div>
  );
}
