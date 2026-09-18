import LoadingScreen from "./LoadingScreen";
import { WifiOff } from "lucide-react";
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
      <LoadingScreen message="กำลังตรวจสอบการเข้าสู่ระบบ…" />
    );
  }

  if (status === "unreachable") {
    return (
      <div className="state-page">
        <div className="state-card"><WifiOff size={30} className="text-teal-300" /><h1 className="panel-title">เชื่อมต่อบริการไม่ได้</h1>
        <p className="text-sm text-navy-300 leading-relaxed">
          Couldn't reach the server to confirm your session. You're still signed
          in — this is a connection problem, not a login problem.
        </p>
        <button
          type="button"
          onClick={refresh}
          className="primary-button"
        >
          Try again
        </button></div>
      </div>
    );
  }

  if (status === "anonymous") return <Navigate to="/login" replace />;
  return children;
}
