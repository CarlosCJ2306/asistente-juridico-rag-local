import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import {
  parsePublicDocument,
  parsePublicDocumentPage,
  type DocumentId,
  type PublicDocument,
  type PublicDocumentPage,
  type PublicDocumentUploadInput,
} from "../types";

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

export async function uploadDocument(input: PublicDocumentUploadInput, signal?: AbortSignal): Promise<PublicDocument> {
  const body = new FormData();
  body.append("file", input.file);
  body.append("document_type", input.documentType);
  body.append("knowledge_layer", input.knowledgeLayer);
  body.append("source_kind", "local_upload");
  if (input.displayName !== undefined) body.append("display_name", input.displayName);
  if (input.expiresAt !== undefined) body.append("expires_at", input.expiresAt);
  return requireData(await apiClient.post(DOCUMENTS_PATH, body, parsePublicDocument, { signal }), 201);
}
