import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "../layouts";
import { DocumentDetailPage, DocumentsPage, DocumentSearchPage } from "../features/documents";
import { HpnMatricesPage, HpnMatrixDetailPage } from "../features/hpn-matrices";
import { LegalNetworkPage } from "../features/legal-network";
import { ModelsPage } from "../features/models";
import { ChatPage } from "../features/chat";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "documents", element: <DocumentsPage /> },
      { path: "documents/search", element: <DocumentSearchPage /> },
      { path: "documents/:documentId", element: <DocumentDetailPage /> },
      { path: "matrices-hpn", element: <HpnMatricesPage /> },
      { path: "matrices-hpn/:matrixId", element: <HpnMatrixDetailPage /> },
      { path: "legal-network", element: <LegalNetworkPage /> },
      { path: "legal-network/:matrixId", element: <LegalNetworkPage /> },
      { path: "models", element: <ModelsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
