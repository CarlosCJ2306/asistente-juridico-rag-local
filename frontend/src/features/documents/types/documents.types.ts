export type DocumentId = string & { readonly __documentId: unique symbol };

export type DocumentType = "expediente" | "normativa" | "jurisprudencia" | "otro";
export type DocumentStatus =
  | "registered"
  | "stored"
  | "pending_extraction"
  | "extracting"
  | "extracted"
  | "extraction_failed"
  | "failed"
  | "archived";
export type KnowledgeLayer = "managed_corpus" | "private_library" | "temporary" | "web_verified" | "global_candidate";
export type SourceKind = "local_upload" | "managed_import" | "web_import";
export type ReviewStatus = "not_required" | "pending" | "approved" | "rejected" | "archived";
export type LegalValidityStatus = "unknown" | "current" | "superseded" | "repealed" | "expired";
export type IndexStatus = "not_requested" | "pending" | "indexing" | "indexed" | "failed" | "excluded";
export type RagEligibilityReason =
  | "document_deleted"
  | "document_archived"
  | "extraction_incomplete"
  | "review_pending"
  | "review_rejected"
  | "legal_validity_not_allowed"
  | "temporary_expiration_missing"
  | "temporary_expired"
  | "expiration_not_allowed"
  | "layer_not_rag_eligible"
  | "index_not_ready";

export interface PublicDocument {
  readonly id: DocumentId;
  readonly displayName: string;
  readonly originalFilename: string;
  readonly documentType: DocumentType;
  readonly mimeType: string;
  readonly extension: string;
  readonly sizeBytes: number;
  readonly status: DocumentStatus;
  readonly knowledgeLayer: KnowledgeLayer;
  readonly sourceKind: SourceKind;
  readonly reviewStatus: ReviewStatus;
  readonly legalValidityStatus: LegalValidityStatus;
  readonly indexStatus: IndexStatus;
  readonly issuingEntity: string | null;
  readonly jurisdiction: string | null;
  readonly legalArea: string | null;
  readonly canonicalSourceUrl: string | null;
  readonly publishedAt: string | null;
  readonly sourceAccessedAt: string | null;
  readonly versionLabel: string | null;
  readonly expiresAt: string | null;
  readonly archivedAt: string | null;
  readonly supersedesDocumentId: DocumentId | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly ragEligible: boolean;
  readonly ragEligibilityReasons: readonly RagEligibilityReason[];
  readonly isExpired: boolean;
}

export interface PublicDocumentPage {
  readonly items: readonly PublicDocument[];
  readonly total: number;
  readonly page: number;
  readonly pageSize: number;
}

export type PublicUploadKnowledgeLayer = "private_library" | "temporary";

export interface PublicDocumentUploadInput {
  readonly file: File;
  readonly documentType: DocumentType;
  readonly knowledgeLayer: PublicUploadKnowledgeLayer;
  readonly displayName?: string;
  readonly expiresAt?: string;
}
