import { FileSearch, ArrowLeft } from "lucide-react";
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
    <div className="state-page">
      <div className="state-card">
        <span className="brand-icon"><FileSearch size={24} /></span><p className="eyebrow">URRISK WORKSPACE</p>

        <div className="space-y-2">
          <p className="text-7xl font-semibold text-teal-300/70 tracking-tight tabular-nums">404</p>
          <h1 className="text-lg font-medium text-navy-200">ไม่พบหน้านี้</h1>
          <p className="text-sm text-navy-400">
            ไม่มีหน้าที่อยู่ตรง{" "}
            <span className="font-mono text-navy-400 break-all">{pathname}</span>{" "}
            — ลิงก์อาจเก่า หรือพิมพ์ URL คลาดไป
          </p>
        </div>

        <Link
          to={signedIn ? "/manual" : "/login"}
          className="primary-button"
        >
          <ArrowLeft size={16} />{signedIn ? "กลับไปหน้าหลัก" : "ไปหน้าเข้าสู่ระบบ"}
        </Link>
      </div>
    </div>
  );
}
