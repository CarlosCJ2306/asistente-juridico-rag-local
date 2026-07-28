export type ModelType = "embedding" | "llm";
export type CompatibilityStatus = "compatible" | "inactive" | "not_installed" | "disabled";

export interface CatalogModel {
  readonly modelId: string;
  readonly modelType: ModelType;
  readonly displayName: string;
  readonly description: string;
  readonly family: string;
  readonly format: string;
  readonly quantization: string | null;
  readonly installed: boolean;
  readonly active: boolean;
  readonly loaded: boolean;
  readonly sizeBytes: number | null;
  readonly embeddingDimension: number | null;
  readonly contextLength: number | null;
  readonly capabilities: readonly string[];
  readonly compatibilityStatus: CompatibilityStatus;
}

export interface ModelCatalog { readonly schemaVersion: number; readonly models: readonly CatalogModel[]; }
export interface ModelSelection { readonly schemaVersion: number; readonly activeEmbeddingModelId: string; readonly activeLlmModelId: string; }
export interface EmbeddingRuntimeStatus { readonly modelId: string; readonly state: "unloaded" | "loading" | "loaded" | "error"; readonly localFilesAvailable: boolean; readonly device: string; readonly dimension: number | null; readonly automaticallyLoaded: boolean; }
export interface LlmRuntimeStatus { readonly modelId: string; readonly state: "unloaded" | "loaded"; readonly contextSize: number; }
