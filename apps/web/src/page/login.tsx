import { BackgroundOrbs, GridOverlay, BrandHeader, LoginCard } from "../component/login";

/**
 * LoginPage — assembles the full-screen login view.
 *
 * Layout:
 *   BackgroundOrbs  (fixed, z-0)
 *   GridOverlay     (fixed, z-0)
 *   main            (relative, centered flex column)
 *     BrandHeader   — logo + brand name
 *     LoginCard     — Google OAuth button + sign-up link
 *     footer        — legal links
 */
export default function LoginPage() {
  return (
    <>
      {/* ── Decorative background layers ── */}
      <BackgroundOrbs />
      <GridOverlay />

      {/* ── Page content ── */}
      <main className="relative flex min-h-screen items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm space-y-8">

          {/* Brand header — fades in from below */}
          <div className="animate-fade-in-up">
            <BrandHeader />
          </div>

          {/* Auth card — slightly delayed */}
          <div className="animate-fade-in-up anim-delay-1">
            <LoginCard />
          </div>

          {/* Footer legal */}
          <p className="animate-fade-in-up anim-delay-2 text-center text-xs text-zinc-700">
            By continuing you agree to our{" "}
            <a
              href="#"
              className="text-zinc-600 underline-offset-2 transition-colors hover:text-zinc-400 hover:underline"
            >
              Terms of Service
            </a>{" "}
            &amp;{" "}
            <a
              href="#"
              className="text-zinc-600 underline-offset-2 transition-colors hover:text-zinc-400 hover:underline"
            >
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </main>
    </>
  );
}