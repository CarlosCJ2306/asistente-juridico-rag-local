import type { DocumentId } from "../types";

export const documentKeys = {
  all: ["documents"] as const,
  lists: () => [...documentKeys.all, "list"] as const,
  list: (page: number, pageSize: number) => [...documentKeys.lists(), { page, pageSize }] as const,
  details: () => [...documentKeys.all, "detail"] as const,
  detail: (documentId: DocumentId) => [...documentKeys.details(), documentId] as const,
  pages: (documentId: DocumentId) => [...documentKeys.all, "pages", documentId] as const,
  chunks: (documentId: DocumentId) => [...documentKeys.all, "chunks", documentId] as const,
};
