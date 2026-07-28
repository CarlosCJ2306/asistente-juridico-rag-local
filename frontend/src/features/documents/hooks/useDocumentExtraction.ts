import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useNotifications } from "../../../hooks/useNotifications";
import { documentKeys, extractDocument, getExtractionChunkTotal, getExtractionPageTotal } from "../api";
import type { DocumentId } from "../types";

export function useDocumentExtraction(documentId: DocumentId) {
  const queryClient = useQueryClient(); const { notify } = useNotifications();
  return useMutation({ mutationFn: () => extractDocument(documentId), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: documentKeys.all }); notify({ kind: "success", title: "Extracción completada", message: "Se registraron páginas y fragmentos. La indexación sigue pendiente.", deduplicationKey: "document-extracted" }); } });
}
export function useExtractionTotals(documentId: DocumentId, enabled: boolean) {
  const pages = useQuery({ queryKey: documentKeys.pages(documentId), queryFn: ({ signal }) => getExtractionPageTotal(documentId, signal), enabled });
  const chunks = useQuery({ queryKey: documentKeys.chunks(documentId), queryFn: ({ signal }) => getExtractionChunkTotal(documentId, signal), enabled });
  return { pages, chunks };
}
