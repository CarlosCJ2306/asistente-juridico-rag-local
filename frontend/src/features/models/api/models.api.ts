import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import { parseEmbeddingRuntime, parseLlmRuntime, parseModelCatalog, parseModelSelection } from "../types";
import type { EmbeddingRuntimeStatus, LlmRuntimeStatus, ModelCatalog, ModelSelection, ModelType } from "../types";

function data<T>(response: ApiResponse<T>): T { if (response.status !== 200 || response.data === null) throw createInvalidResponseError(); return response.data; }
export async function getModelCatalog(signal?: AbortSignal): Promise<ModelCatalog> { return data(await apiClient.get("/api/models/catalog", parseModelCatalog, { signal })); }
export async function getModelSelection(signal?: AbortSignal): Promise<ModelSelection> { return data(await apiClient.get("/api/models/selection", parseModelSelection, { signal })); }
export async function selectModel(modelType: ModelType, modelId: string): Promise<ModelSelection> { const endpoint = modelType === "embedding" ? "/api/models/selection/embeddings" : "/api/models/selection/llm"; return data(await apiClient.put(endpoint, { model_id: modelId }, parseModelSelection)); }
export async function getEmbeddingRuntime(signal?: AbortSignal): Promise<EmbeddingRuntimeStatus> { return data(await apiClient.get("/api/models/embeddings/status", parseEmbeddingRuntime, { signal })); }
export async function loadEmbeddingRuntime(): Promise<EmbeddingRuntimeStatus> { return data(await apiClient.post("/api/models/embeddings/load", {}, parseEmbeddingRuntime)); }
export async function unloadEmbeddingRuntime(): Promise<EmbeddingRuntimeStatus> { return data(await apiClient.post("/api/models/embeddings/unload", {}, parseEmbeddingRuntime)); }
export async function getLlmRuntime(signal?: AbortSignal): Promise<LlmRuntimeStatus> { return data(await apiClient.get("/api/models/llm/status", parseLlmRuntime, { signal })); }
export async function loadLlmRuntime(): Promise<LlmRuntimeStatus> { return data(await apiClient.post("/api/models/llm/load", {}, parseLlmRuntime)); }
export async function unloadLlmRuntime(): Promise<LlmRuntimeStatus> { return data(await apiClient.post("/api/models/llm/unload", {}, parseLlmRuntime)); }
