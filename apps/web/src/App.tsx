import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import Login from "./page/login";
import Manual from "./page/manual";
import AuthCallback from "./page/callback";
import RequireAuth from "./component/RequireAuth";
import ContractPage from "./page/contract";
import { getToken } from "./lib/auth";

/**
 * "/" is the login screen for signed-out visitors and a shortcut into the app
 * for everyone else — showing the login form to someone who is already signed
 * in reads like their session was lost.
 *
 * A token is enough to decide *where* to send them; whether it still works is
 * RequireAuth's job, so an expired one bounces straight back here. Checked on
 * render rather than when the router is built, or the answer would be frozen
 * at page load and a logout would still land here.
 */
function RootRoute() {
  return getToken() ? <Navigate to="/manual" replace /> : <Login />;
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootRoute />,
  },
  {
    path: "/login",
    element: <Login />,
  },

  {
    path: "/auth/callback",
    element: <AuthCallback />,
  },
  {
    // Every call this page makes needs a bearer token, so guard it like /manual
    // rather than letting it render and fail with 401s.
    path: "/contract",
    element: (
      <RequireAuth>
        <ContractPage />
      </RequireAuth>
    ),
  },
  {
    path: "/manual",
    element: (
      <RequireAuth>
        <Manual />
      </RequireAuth>
    ),
  },

]);

export default function App() {
  return <RouterProvider router={router} />;
}
