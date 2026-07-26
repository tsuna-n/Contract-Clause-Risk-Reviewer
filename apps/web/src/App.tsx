import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import Login from "./page/login";
import AuthCallback from "./page/callback";
import RequireAuth from "./component/RequireAuth";
import { getToken } from "./lib/auth";
import AuthProvider from "./component/AuthProvider";
import Chat from "./page/layout/chat-layout";
import ContractPage from "./page/contract";
import PlaybookPage from "./page/playbook";
import EvaluatePage from "./page/evaluate";
import SystemPage from "./page/system";

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
    // Playbook management (CRUD) + semantic search. Reached from the sidebar's
    // Tools links; guarded like the rest of the app even though the playbook
    // API itself doesn't require a bearer token.
    path: "/playbook",
    element: (
      <RequireAuth>
        <PlaybookPage />
      </RequireAuth>
    ),
  },
  {
    // Evaluation harness: runs the pipeline against a gold set and reports
    // accuracy metrics. Long-running, so it lives on its own page.
    path: "/evaluate",
    element: (
      <RequireAuth>
        <EvaluatePage />
      </RequireAuth>
    ),
  },
  {
    // System status: pings the root + /health + /health/db probes.
    path: "/system",
    element: (
      <RequireAuth>
        <SystemPage />
      </RequireAuth>
    ),
  },
  {
    // The signed-in home: review history on the left, upload or the selected
    // report on the right.
    path: "/manual",
    element: (
      <RequireAuth>
        <Chat />
      </RequireAuth>
    ),
  },
  // Earlier names for the same screen. Redirects rather than three routes
  // rendering one component, so there is a single URL to link to and old
  // bookmarks still land somewhere.
  { path: "/chat", element: <Navigate to="/manual" replace /> },
  { path: "/layout/chat-layout", element: <Navigate to="/manual" replace /> },
]);

export default function App() {
  // AuthProvider sits above the router so the signed-in user survives
  // navigation: fetched once on load, not re-fetched on every route change.
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
