import { apiClient, createInvalidResponseError, type ApiResponse, type JsonValue } from "../../../api";
import { parseConversation, parseConversationDetail, parseConversationPage, parseConversationTurn, type ConversationDetail, type ConversationInput, type ConversationPage, type ConversationStatus, type ConversationSummary, type ConversationTurn } from "../types";

const PATH = "/api/conversations";
const cookieOptions = { credentials: "same-origin" as const, timeoutMs: 120_000 };
function data<T>(response: ApiResponse<T>, status: number): T { if(response.status !== status || response.data === null) throw createInvalidResponseError(); return response.data; }
function itemPath(id: string): string { return `${PATH}/${encodeURIComponent(id)}`; }
function body(input: ConversationInput): Record<string, JsonValue> { const value: Record<string, JsonValue>={question:input.question,text_match_mode:input.textMatchMode,top_k:input.topK}; if(input.documentId)value.document_id=input.documentId; if(input.documentTypes?.length)value.document_types=[...input.documentTypes]; if(input.knowledgeLayers?.length)value.knowledge_layers=[...input.knowledgeLayers]; if(input.minPage!==undefined)value.min_page=input.minPage; if(input.maxPage!==undefined)value.max_page=input.maxPage; return value; }
export async function listConversations(page = 1, pageSize = 20, status: ConversationStatus = "active", signal?: AbortSignal): Promise<ConversationPage> { return data(await apiClient.get(PATH,parseConversationPage,{...cookieOptions,signal,query:{page,page_size:pageSize,status}}),200); }
export async function getConversation(id: string, signal?: AbortSignal): Promise<ConversationDetail> { return data(await apiClient.get(itemPath(id),parseConversationDetail,{...cookieOptions,signal}),200); }
export async function createConversation(signal?: AbortSignal): Promise<ConversationSummary> { return data(await apiClient.post(PATH,{},parseConversation,{...cookieOptions,signal}),201); }
export async function updateConversation(id:string, update:{title?:string;status?:ConversationStatus}):Promise<ConversationSummary>{ return data(await apiClient.patch(itemPath(id),update,parseConversation,cookieOptions),200); }
export async function deleteConversation(id:string):Promise<void>{ const response=await apiClient.delete(itemPath(id),(value)=>value,cookieOptions); if(response.status!==204)throw createInvalidResponseError(); }
export async function sendConversationMessage(id:string,input:ConversationInput,idempotencyKey:string,signal?:AbortSignal):Promise<ConversationTurn>{ return data(await apiClient.post(itemPath(id)+"/messages",body(input),parseConversationTurn,{...cookieOptions,signal,headers:{"Idempotency-Key":idempotencyKey}}),201); }
