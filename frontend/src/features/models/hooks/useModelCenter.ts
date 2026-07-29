import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getEmbeddingRuntime, getLlmRuntime, getModelCatalog, getModelSelection, loadEmbeddingRuntime, loadLlmRuntime, modelKeys, selectModel, unloadEmbeddingRuntime, unloadLlmRuntime } from "../api";
import type { ModelType } from "../types";
import { getSemanticStatus, semanticIndexKeys } from "../../documents";

export function useModelCenter() {
  const queryClient = useQueryClient();
  const catalog = useQuery({ queryKey: modelKeys.catalog, queryFn: ({ signal }) => getModelCatalog(signal) });
  const selection = useQuery({ queryKey: modelKeys.selection, queryFn: ({ signal }) => getModelSelection(signal) });
  const embeddingStatus = useQuery({ queryKey: modelKeys.embeddingStatus, queryFn: ({ signal }) => getEmbeddingRuntime(signal) });
  const llmStatus = useQuery({ queryKey: modelKeys.llmStatus, queryFn: ({ signal }) => getLlmRuntime(signal) });
  const semanticStatus = useQuery({ queryKey: semanticIndexKeys.status, queryFn: ({ signal }) => getSemanticStatus(signal) });
  const refreshModels = async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: modelKeys.all }), queryClient.invalidateQueries({ queryKey: semanticIndexKeys.all })]); };
  const select = useMutation({ mutationFn: ({ modelType, modelId }: { readonly modelType: ModelType; readonly modelId: string }) => selectModel(modelType, modelId), onSuccess: refreshModels });
  const loadEmbedding = useMutation({ mutationFn: loadEmbeddingRuntime, onSuccess: refreshModels });
  const unloadEmbedding = useMutation({ mutationFn: unloadEmbeddingRuntime, onSuccess: refreshModels });
  const loadLlm = useMutation({ mutationFn: loadLlmRuntime, onSuccess: refreshModels });
  const unloadLlm = useMutation({ mutationFn: unloadLlmRuntime, onSuccess: refreshModels });
  return { catalog, selection, embeddingStatus, llmStatus, semanticStatus, select, loadEmbedding, unloadEmbedding, loadLlm, unloadLlm };
}
