import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useNotifications } from "../../../hooks";
import { documentKeys, uploadDocument } from "../api";
import type { PublicDocumentUploadInput } from "../types";

export function useDocumentUpload() {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: (input: PublicDocumentUploadInput) => uploadDocument(input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
      notify({ kind: "success", title: "Documento registrado", message: "El documento quedó pendiente de procesamiento e indexación.", deduplicationKey: "document-uploaded" });
    },
  });
}
