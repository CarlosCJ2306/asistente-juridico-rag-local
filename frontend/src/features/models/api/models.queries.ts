export const modelKeys = {
  all: ["models"] as const,
  catalog: ["models", "catalog"] as const,
  selection: ["models", "selection"] as const,
  embeddingStatus: ["semantic-index", "model"] as const,
  llmStatus: ["models", "llm-status"] as const,
};
