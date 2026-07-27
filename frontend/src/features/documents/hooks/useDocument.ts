import { useQuery } from "@tanstack/react-query";

import { documentKeys, getDocument } from "../api";
import type { DocumentId } from "../types";

export function useDocument(documentId: DocumentId) {
  return useQuery({
    queryKey: documentKeys.detail(documentId),
    queryFn: ({ signal }) => getDocument(documentId, signal),
  });
}
