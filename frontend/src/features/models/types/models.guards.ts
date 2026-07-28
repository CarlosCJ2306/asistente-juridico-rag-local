import { createInvalidResponseError } from "../../../api";
import type { CatalogModel, CompatibilityStatus, EmbeddingRuntimeStatus, LlmRuntimeStatus, ModelCatalog, ModelSelection, ModelType } from "./models.types";

function record(value: unknown): Record<string, unknown> { if (typeof value !== "object" || value === null || Array.isArray(value)) throw createInvalidResponseError(); return value as Record<string, unknown>; }
function text(value: unknown): string { if (typeof value !== "string" || !value.trim()) throw createInvalidResponseError(); return value; }
function positiveInteger(value: unknown): number { if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) throw createInvalidResponseError(); return value; }
function nonNegativeInteger(value: unknown): number { if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw createInvalidResponseError(); return value; }
function nullablePositiveInteger(value: unknown): number | null { return value === null ? null : positiveInteger(value); }
function enumeration<T extends string>(value: unknown, values: readonly T[]): T { if (typeof value !== "string" || !values.includes(value as T)) throw createInvalidResponseError(); return value as T; }

function parseCatalogModel(value: unknown): CatalogModel {
  const item = record(value);
  if (typeof item.installed !== "boolean" || typeof item.active !== "boolean" || typeof item.loaded !== "boolean" || !Array.isArray(item.capabilities)) throw createInvalidResponseError();
  const capabilities = item.capabilities.map(text);
  if (new Set(capabilities).size !== capabilities.length) throw createInvalidResponseError();
  return {
    modelId: text(item.model_id), modelType: enumeration<ModelType>(item.model_type, ["embedding", "llm"]), displayName: text(item.display_name), description: text(item.description), family: text(item.family), format: text(item.format), quantization: item.quantization === null ? null : text(item.quantization), installed: item.installed, active: item.active, loaded: item.loaded, sizeBytes: item.size_bytes === null ? null : nonNegativeInteger(item.size_bytes), embeddingDimension: nullablePositiveInteger(item.embedding_dimension), contextLength: nullablePositiveInteger(item.context_length), capabilities, compatibilityStatus: enumeration<CompatibilityStatus>(item.compatibility_status, ["compatible", "inactive", "not_installed", "disabled"]),
  };
}

export function parseModelCatalog(value: unknown): ModelCatalog { const item = record(value); if (!Array.isArray(item.models)) throw createInvalidResponseError(); const models = item.models.map(parseCatalogModel); if (new Set(models.map((model) => model.modelId)).size !== models.length) throw createInvalidResponseError(); return { schemaVersion: positiveInteger(item.schema_version), models }; }
export function parseModelSelection(value: unknown): ModelSelection { const item = record(value); return { schemaVersion: positiveInteger(item.schema_version), activeEmbeddingModelId: text(item.active_embedding_model_id), activeLlmModelId: text(item.active_llm_model_id) }; }
export function parseEmbeddingRuntime(value: unknown): EmbeddingRuntimeStatus { const item = record(value); if (typeof item.local_files_available !== "boolean" || typeof item.device !== "string" || (item.automatically_loaded !== undefined && typeof item.automatically_loaded !== "boolean")) throw createInvalidResponseError(); return { modelId: text(item.model), state: enumeration(item.state, ["unloaded", "loading", "loaded", "error"]), localFilesAvailable: item.local_files_available, device: item.device, dimension: nullablePositiveInteger(item.dimension), automaticallyLoaded: item.automatically_loaded === true }; }
export function parseLlmRuntime(value: unknown): LlmRuntimeStatus { const item = record(value); return { modelId: text(item.model), state: enumeration(item.state, ["unloaded", "loaded"]), contextSize: positiveInteger(item.context_size) }; }
