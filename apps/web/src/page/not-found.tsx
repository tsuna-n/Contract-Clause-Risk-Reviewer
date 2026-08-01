import { Link, useLocation } from "react-router-dom";
import { getToken } from "../lib/auth";

/**
 * The catch-all for URLs no route matches.
 *
 * Without it react-router falls through to its own ErrorBoundary, which prints
 * "Unexpected Application Error!" and a note addressed to the developer — a
 * stack-trace screen shown to whoever mistyped a URL, with no way back.
 *
 * Where "back" leads depends on whether there's a session: sending a signed-out
 * visitor to /manual only bounces them through the route guard to /login, and
 * sending a signed-in one to /login reads like their session was lost. Same
 * reasoning as RootRoute in App.tsx.
 */
export default function NotFoundPage() {
  const { pathname } = useLocation();
  const signedIn = getToken() !== null;

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-md w-full text-center space-y-5">
        <p className="text-amber-500 font-serif text-xl font-bold tracking-wide">
          Contract Risk Reviewer
        </p>

        <div className="space-y-2">
          <p className="text-6xl font-semibold text-neutral-700 tabular-nums">404</p>
          <h1 className="text-lg font-medium text-neutral-200">ไม่พบหน้านี้</h1>
          <p className="text-sm text-neutral-500">
            ไม่มีหน้าที่อยู่ตรง{" "}
            <span className="font-mono text-neutral-400 break-all">{pathname}</span>{" "}
            — ลิงก์อาจเก่า หรือพิมพ์ URL คลาดไป
          </p>
        </div>

        <Link
          to={signedIn ? "/manual" : "/login"}
          className="inline-block px-4 py-2 text-sm font-medium rounded-lg bg-neutral-800 text-neutral-200 hover:bg-neutral-700 transition"
        >
          {signedIn ? "← กลับไปหน้าหลัก" : "← ไปหน้าเข้าสู่ระบบ"}
        </Link>
      </div>
    </div>
  );
}
