import type {
  DocumentId,
  DocumentStatus,
  DocumentType,
  IndexStatus,
  KnowledgeLayer,
  LegalValidityStatus,
  PublicDocument,
  PublicDocumentPage,
  RagEligibilityReason,
  ReviewStatus,
  SourceKind,
} from "./documents.types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const FORBIDDEN_FIELDS = ["stored_filename", "relative_path", "sha256", "error_code", "error_message"] as const;

function invalidResponse(): never {
  throw new Error("DOCUMENTS_RESPONSE_INVALID");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : invalidResponse();
}

function stringValue(value: unknown, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.trim() === "")) return invalidResponse();
  return value;
}

function nullableString(value: unknown): string | null {
  return value === null ? null : stringValue(value);
}

function integer(value: unknown, minimum = 0): number {
  if (!Number.isInteger(value) || typeof value !== "number" || value < minimum) return invalidResponse();
  return value;
}

function booleanValue(value: unknown): boolean {
  return typeof value === "boolean" ? value : invalidResponse();
}

function timestamp(value: unknown): string {
  const result = stringValue(value);
  return Number.isNaN(Date.parse(result)) ? invalidResponse() : result;
}

function nullableTimestamp(value: unknown): string | null {
  return value === null ? null : timestamp(value);
}

export function isDocumentId(value: unknown): value is DocumentId {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function documentId(value: unknown): DocumentId {
  return isDocumentId(value) ? value : invalidResponse();
}

function enumValue<T extends string>(value: unknown, values: readonly T[]): T {
  return typeof value === "string" && values.includes(value as T) ? (value as T) : invalidResponse();
}

function rejectInternalFields(item: Record<string, unknown>): void {
  if (FORBIDDEN_FIELDS.some((field) => Object.hasOwn(item, field))) invalidResponse();
}

export function parsePublicDocument(value: unknown): PublicDocument {
  const item = record(value);
  rejectInternalFields(item);
  const createdAt = timestamp(item.created_at);
  const updatedAt = timestamp(item.updated_at);
  if (Date.parse(updatedAt) < Date.parse(createdAt)) invalidResponse();
  const ragEligibilityReasons = Array.isArray(item.rag_eligibility_reasons)
    ? item.rag_eligibility_reasons.map((reason) => enumValue<RagEligibilityReason>(reason, [
      "document_deleted", "document_archived", "extraction_incomplete", "review_pending", "review_rejected",
      "legal_validity_not_allowed", "temporary_expiration_missing", "temporary_expired", "expiration_not_allowed",
      "layer_not_rag_eligible", "index_not_ready",
    ]))
    : invalidResponse();
  return {
    id: documentId(item.id),
    displayName: stringValue(item.display_name),
    originalFilename: stringValue(item.original_filename),
    documentType: enumValue<DocumentType>(item.document_type, ["expediente", "normativa", "jurisprudencia", "otro"]),
    mimeType: stringValue(item.mime_type),
    extension: stringValue(item.extension),
    sizeBytes: integer(item.size_bytes),
    status: enumValue<DocumentStatus>(item.status, ["registered", "stored", "pending_extraction", "extracting", "extracted", "extraction_failed", "failed", "archived"]),
    knowledgeLayer: enumValue<KnowledgeLayer>(item.knowledge_layer, ["managed_corpus", "private_library", "temporary", "web_verified", "global_candidate"]),
    sourceKind: enumValue<SourceKind>(item.source_kind, ["local_upload", "managed_import", "web_import"]),
    reviewStatus: enumValue<ReviewStatus>(item.review_status, ["not_required", "pending", "approved", "rejected", "archived"]),
    legalValidityStatus: enumValue<LegalValidityStatus>(item.legal_validity_status, ["unknown", "current", "superseded", "repealed", "expired"]),
    indexStatus: enumValue<IndexStatus>(item.index_status, ["not_requested", "pending", "indexing", "indexed", "failed", "excluded"]),
    issuingEntity: nullableString(item.issuing_entity),
    jurisdiction: nullableString(item.jurisdiction),
    legalArea: nullableString(item.legal_area),
    canonicalSourceUrl: nullableString(item.canonical_source_url),
    publishedAt: nullableTimestamp(item.published_at),
    sourceAccessedAt: nullableTimestamp(item.source_accessed_at),
    versionLabel: nullableString(item.version_label),
    expiresAt: nullableTimestamp(item.expires_at),
    archivedAt: nullableTimestamp(item.archived_at),
    supersedesDocumentId: item.supersedes_document_id === null ? null : documentId(item.supersedes_document_id),
    createdAt,
    updatedAt,
    ragEligible: booleanValue(item.rag_eligible),
    ragEligibilityReasons,
    isExpired: booleanValue(item.is_expired),
  };
}

export function parsePublicDocumentPage(value: unknown): PublicDocumentPage {
  const response = record(value);
  if (!Array.isArray(response.items)) invalidResponse();
  const items = response.items.map(parsePublicDocument);
  if (new Set(items.map((item) => item.id)).size !== items.length) invalidResponse();
  const pageSize = integer(response.page_size, 1);
  if (pageSize > 100) invalidResponse();
  return { items, total: integer(response.total), page: integer(response.page, 1), pageSize };
}
