import type { DocumentId, DocumentType, KnowledgeLayer } from "./documents.types";

export type TextMatchMode = "all_terms" | "any_term" | "phrase";

export interface HybridSearchInput {
  readonly query: string; readonly textMatchMode: TextMatchMode; readonly topK: number; readonly documentId?: string; readonly documentTypes?: readonly string[]; readonly knowledgeLayers?: readonly string[]; readonly minPage?: number; readonly maxPage?: number;
}
export interface HybridSearchItem {
  readonly chunkId: string; readonly documentId: DocumentId; readonly documentName: string; readonly documentType: DocumentType; readonly knowledgeLayer: KnowledgeLayer; readonly chunkIndex: number; readonly startPage: number; readonly endPage: number; readonly snippet: string; readonly hybridScore: number; readonly textRank: number | null; readonly semanticRank: number | null;
}
export interface HybridSearchResponse { readonly items: readonly HybridSearchItem[]; readonly returned: number; readonly topK: number; }
