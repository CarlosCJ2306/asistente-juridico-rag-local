import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import { parsePublicDocument, parsePublicDocumentPage, type DocumentId, type PublicDocument, type PublicDocumentPage } from "../types";

const DOCUMENTS_PATH = "/api/documents";

function requireData<T>(response: ApiResponse<T>, expectedStatus: number): T {
  if (response.status !== expectedStatus || response.data === null) throw createInvalidResponseError();
  return response.data;
}

function resourcePath(documentId: DocumentId): string {
  return `${DOCUMENTS_PATH}/${encodeURIComponent(documentId)}`;
}

export async function listDocuments(page: number, pageSize: number, signal?: AbortSignal): Promise<PublicDocumentPage> {
  const response = await apiClient.get(DOCUMENTS_PATH, parsePublicDocumentPage, {
    query: { page, page_size: pageSize },
    signal,
  });
  return requireData(response, 200);
}

export async function getDocument(documentId: DocumentId, signal?: AbortSignal): Promise<PublicDocument> {
  return requireData(await apiClient.get(resourcePath(documentId), parsePublicDocument, { signal }), 200);
}
