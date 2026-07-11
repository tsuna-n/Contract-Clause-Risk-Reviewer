import { Navigate } from "react-router-dom";
import { getToken } from "../lib/auth";

/**
 * RequireAuth — route guard. Without this, protected pages like
 * /manual render regardless of login state, so deleting the token
 * has no visible effect until a guard actually checks it.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}
