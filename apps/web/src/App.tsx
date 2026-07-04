import { createBrowserRouter, RouterProvider } from "react-router-dom";
import Login from "./page/login";
import Manual from "./page/manual";


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
    path: "/manual",
    element: <Manual />,
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
