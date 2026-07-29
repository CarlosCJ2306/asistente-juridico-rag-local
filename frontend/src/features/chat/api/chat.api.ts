import { apiClient, createInvalidResponseError, type ApiResponse, type JsonValue } from "../../../api";
import { parseRagChatResponse, type RagChatInput, type RagChatResponse } from "../types";

const RAG_CHAT_PATH = "/api/chat/rag";

function requireData<T>(response: ApiResponse<T>, expectedStatus: number): T {
  if (response.status !== expectedStatus || response.data === null) throw createInvalidResponseError();
  return response.data;
}

export async function askRagChat(input: RagChatInput, signal?: AbortSignal): Promise<RagChatResponse> {
  const body: Record<string, JsonValue> = {
    question: input.question,
    text_match_mode: input.textMatchMode,
    top_k: input.topK,
  };
  if (input.documentId) body.document_id = input.documentId;
  if (input.documentTypes?.length) body.document_types = input.documentTypes;
  if (input.knowledgeLayers?.length) body.knowledge_layers = input.knowledgeLayers;
  if (input.minPage !== undefined) body.min_page = input.minPage;
  if (input.maxPage !== undefined) body.max_page = input.maxPage;
  return requireData(await apiClient.post(RAG_CHAT_PATH, body, parseRagChatResponse, { signal, timeoutMs: 120_000 }), 200);
}
