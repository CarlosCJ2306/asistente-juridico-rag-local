import { isDocumentId, type DocumentId, type DocumentType, type KnowledgeLayer } from "../../documents/types";
import type { RagChatResponse, RagCitation } from "./chat.types";

const MARKER_PATTERN = /^\[F[1-9]\d*\]$/u;
const DOCUMENT_TYPES: readonly DocumentType[] = ["expediente", "normativa", "jurisprudencia", "otro"];
const KNOWLEDGE_LAYERS: readonly KnowledgeLayer[] = ["managed_corpus", "private_library", "temporary", "web_verified", "global_candidate"];
const FORBIDDEN_FIELDS = ["stored_filename", "relative_path", "sha256", "chunk_id", "prompt", "context", "vectors", "embeddings"] as const;

function invalidResponse(): never {
  throw new Error("CHAT_RESPONSE_INVALID");
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : invalidResponse();
}

function stringValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : invalidResponse();
}

function integer(value: unknown, minimum = 0): number {
  return typeof value === "number" && Number.isInteger(value) && value >= minimum ? value : invalidResponse();
}

function enumValue<T extends string>(value: unknown, values: readonly T[]): T {
  return typeof value === "string" && values.includes(value as T) ? value as T : invalidResponse();
}

function citation(value: unknown): RagCitation {
  const item = record(value);
  if (FORBIDDEN_FIELDS.some((field) => Object.hasOwn(item, field))) invalidResponse();
  const startPage = integer(item.start_page, 1);
  const endPage = integer(item.end_page, 1);
  if (endPage < startPage) invalidResponse();
  const marker = stringValue(item.marker);
  if (!isDocumentId(item.document_id) || !MARKER_PATTERN.test(marker)) invalidResponse();
  return {
    marker,
    documentId: item.document_id as DocumentId,
    documentName: stringValue(item.document_name),
    displayName: stringValue(item.display_name),
    documentType: enumValue(item.document_type, DOCUMENT_TYPES),
    knowledgeLayer: enumValue(item.knowledge_layer, KNOWLEDGE_LAYERS),
    chunkIndex: integer(item.chunk_index, 1),
    startPage,
    endPage,
  };
}

export function parseRagChatResponse(value: unknown): RagChatResponse {
  const response = record(value);
  if (FORBIDDEN_FIELDS.some((field) => Object.hasOwn(response, field)) || !Array.isArray(response.citations)) invalidResponse();
  const status = enumValue(response.status, ["answered", "insufficient_context"] as const);
  const citations = response.citations.map(citation);
  const citationCount = integer(response.citation_count);
  const contextChunks = integer(response.context_chunks);
  const contextTokens = integer(response.context_tokens);
  const retrievedChunks = integer(response.retrieved_chunks);
  if (
    response.requires_professional_review !== true
    || citationCount !== citations.length
    || contextChunks > retrievedChunks
    || citationCount > contextChunks
    || new Set(citations.map((item) => item.marker)).size !== citations.length
  ) invalidResponse();
  if (status === "answered" && citationCount === 0) invalidResponse();
  if (status === "insufficient_context" && (citationCount !== 0 || contextChunks !== 0 || contextTokens !== 0)) invalidResponse();
  return {
    status,
    answer: stringValue(response.answer),
    retrievedChunks,
    contextChunks,
    contextTokens,
    requiresProfessionalReview: true,
    citationCount,
    citations,
  };
}
