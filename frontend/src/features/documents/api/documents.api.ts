import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import {
  parsePublicDocument,
  parsePublicDocumentPage,
  type DocumentId,
  type PublicDocument,
  type PublicDocumentPage,
  type ExtractionSummary,
  type ExtractionTotals,
  type PublicDocumentUploadInput,
} from "../types";

const DOCUMENTS_PATH = "/api/documents";

function requireData<T>(response: ApiResponse<T>, expectedStatus: number): T {
  if (response.status !== expectedStatus || response.data === null) throw createInvalidResponseError();
  return response.data;
}

function parseExtractionSummary(value: unknown): ExtractionSummary {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw createInvalidResponseError();
  const item = value as Record<string, unknown>;
  const totalPages = item.total_pages; const totalChunks = item.total_chunks;
  if (item.status !== "extracted" || typeof totalPages !== "number" || typeof totalChunks !== "number" || !Number.isInteger(totalPages) || !Number.isInteger(totalChunks) || totalPages < 0 || totalChunks < 0) throw createInvalidResponseError();
  return { status: item.status, totalPages, totalChunks };
}

function parseExtractionTotals(value: unknown): ExtractionTotals {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw createInvalidResponseError();
  const item = value as Record<string, unknown>;
  const total = item.total;
  if (!Array.isArray(item.items) || typeof total !== "number" || !Number.isInteger(total) || total < 0 || !Number.isInteger(item.page) || !Number.isInteger(item.page_size)) throw createInvalidResponseError();
  return { total };
}

export async function extractDocument(documentId: DocumentId, signal?: AbortSignal): Promise<ExtractionSummary> {
  return requireData(await apiClient.post(`${resourcePath(documentId)}/extract`, {}, parseExtractionSummary, { signal }), 200);
}

export async function getExtractionPageTotal(documentId: DocumentId, signal?: AbortSignal): Promise<ExtractionTotals> {
  return requireData(await apiClient.get(`${resourcePath(documentId)}/pages`, parseExtractionTotals, { query: { page: 1, page_size: 1 }, signal }), 200);
}

export async function getExtractionChunkTotal(documentId: DocumentId, signal?: AbortSignal): Promise<ExtractionTotals> {
  return requireData(await apiClient.get(`${resourcePath(documentId)}/chunks`, parseExtractionTotals, { query: { page: 1, page_size: 1 }, signal }), 200);
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
