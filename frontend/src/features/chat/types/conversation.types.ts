import type { DocumentType, KnowledgeLayer } from "../../documents";
import type { RagChatInput } from "./chat.types";

export type ConversationStatus = "active" | "archived";
export type CoverageStatus = "full" | "partial" | "insufficient";
export type MessageStatus = "answered" | "partial" | "insufficient_context" | "failed";

export interface ConversationSummary {
  readonly id: string;
  readonly title: string;
  readonly ownerType: "guest" | "account";
  readonly status: ConversationStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly lastActivityAt: string;
  readonly expiresAt: string | null;
  readonly messageCount: number;
}

export interface ConversationCitation {
  readonly id: string;
  readonly marker: string;
  readonly documentId: string;
  readonly displayName: string;
  readonly documentType: DocumentType;
  readonly knowledgeLayer: KnowledgeLayer;
  readonly issuingEntity: string | null;
  readonly documentDate: string | null;
  readonly startPage: number;
  readonly endPage: number;
  readonly chunkIndex: number;
  readonly locatorLabel: string | null;
  readonly directQuote: string;
  readonly quoteTruncated: boolean;
  readonly citationOrder: number;
  readonly documentAvailable: boolean;
}

export interface ConversationClaim {
  readonly id: string;
  readonly statement: string;
  readonly claimOrder: number;
  readonly supported: boolean;
  readonly citationIds: readonly string[];
}

export interface ConversationMessage {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly sequenceNumber: number;
  readonly publicStatus: MessageStatus | null;
  readonly coverageStatus: CoverageStatus | null;
  readonly createdAt: string;
  readonly completedAt: string | null;
  readonly errorCode: string | null;
  readonly citations: readonly ConversationCitation[];
  readonly claims: readonly ConversationClaim[];
  readonly unsupportedPoints: readonly string[];
}

export interface ConversationDetail extends ConversationSummary {
  readonly messages: readonly ConversationMessage[];
}

export interface ConversationPage { readonly items: readonly ConversationSummary[]; readonly total: number; readonly page: number; readonly pageSize: number; }
export interface ConversationTurn { readonly conversation: ConversationSummary; readonly userMessage: ConversationMessage; readonly assistantMessage: ConversationMessage; }
export type ConversationInput = RagChatInput;
