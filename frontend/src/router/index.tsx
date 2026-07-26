import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../layouts";
import { HpnMatricesPage, HpnMatrixDetailPage } from "../features/hpn-matrices";
import { LegalNetworkPage } from "../features/legal-network";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "matrices-hpn", element: <HpnMatricesPage /> },
      { path: "matrices-hpn/:matrixId", element: <HpnMatrixDetailPage /> },
      { path: "legal-network", element: <LegalNetworkPage /> },
      { path: "legal-network/:matrixId", element: <LegalNetworkPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
