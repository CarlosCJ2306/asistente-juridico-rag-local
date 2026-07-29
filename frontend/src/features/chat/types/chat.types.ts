import type { DocumentId, DocumentType, KnowledgeLayer } from "../../documents/types";
import type { TextMatchMode } from "../../documents/types";

export interface RagChatInput {
  readonly question: string;
  readonly textMatchMode: TextMatchMode;
  readonly topK: number;
  readonly documentId?: string;
  readonly documentTypes?: readonly DocumentType[];
  readonly knowledgeLayers?: readonly KnowledgeLayer[];
  readonly minPage?: number;
  readonly maxPage?: number;
}

export interface RagCitation {
  readonly marker: string;
  readonly documentId: DocumentId;
  readonly documentName: string;
  readonly displayName: string;
  readonly documentType: DocumentType;
  readonly knowledgeLayer: KnowledgeLayer;
  readonly chunkIndex: number;
  readonly startPage: number;
  readonly endPage: number;
}

export interface RagChatResponse {
  readonly status: "answered" | "insufficient_context";
  readonly answer: string;
  readonly retrievedChunks: number;
  readonly contextChunks: number;
  readonly contextTokens: number;
  readonly requiresProfessionalReview: true;
  readonly citationCount: number;
  readonly citations: readonly RagCitation[];
}
