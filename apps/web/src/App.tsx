import { createBrowserRouter, RouterProvider } from "react-router-dom";
import Login from "./page/login";
import Manual from "./page/manual";
import AuthCallback from "./page/callback";
import RequireAuth from "./component/RequireAuth";
import ContractPage from "./page/contract";


const router = createBrowserRouter([
  {
    path: "/",
    element: <Login />,

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
    path: "/contract",
    element: <ContractPage />,
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
