import { useState } from "react";
import { Alert, EmptyState, ErrorState, Stack, Text } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { ModelCard, ModelSelectionModal, SemanticIndexSummary } from "../components";
import { useModelCenter } from "../hooks";
import type { ModelType } from "../types";
import { modelErrorMessage } from "../utils";

export function ModelsPage() {
  const center = useModelCenter();
  const [selectionType, setSelectionType] = useState<ModelType | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const catalog = center.catalog.data?.models ?? [];
  const activeEmbeddingId = center.selection.data?.activeEmbeddingModelId ?? "";
  const activeLlmId = center.selection.data?.activeLlmModelId ?? "";
  const embedding = catalog.find((model) => model.modelId === activeEmbeddingId && model.modelType === "embedding");
  const llm = catalog.find((model) => model.modelId === activeLlmId && model.modelType === "llm");
  const embeddingBusy = center.loadEmbedding.isPending || center.unloadEmbedding.isPending;
  const llmBusy = center.loadLlm.isPending || center.unloadLlm.isPending;
  const queryError = center.catalog.error ?? center.selection.error ?? center.embeddingStatus.error ?? center.llmStatus.error;
  const operationError = center.select.error ?? center.loadEmbedding.error ?? center.unloadEmbedding.error ?? center.loadLlm.error ?? center.unloadLlm.error;
  function confirmSelection(modelId: string) { if (selectionType === null) return; center.select.mutate({ modelType: selectionType, modelId }, { onSuccess: () => { setNotice(selectionType === "embedding" ? "El modelo de embeddings fue seleccionado. El índice semántico debe reconstruirse antes de realizar búsquedas." : "El modelo generativo fue seleccionado. Se usará en la próxima carga y el índice documental no fue modificado."); setSelectionType(null); } }); }
  if (center.catalog.isPending || center.selection.isPending) return <ContentLayout title="Modelos locales" description="Catálogo y ciclo de vida de modelos permitidos."><Text aria-live="polite">Consultando catálogo local…</Text></ContentLayout>;
  if (queryError) return <ContentLayout title="Modelos locales" description="Catálogo y ciclo de vida de modelos permitidos."><ErrorState title="No fue posible consultar los modelos" message={modelErrorMessage(queryError)} /></ContentLayout>;
  if (catalog.length === 0) return <ContentLayout title="Modelos locales" description="Catálogo y ciclo de vida de modelos permitidos."><EmptyState title="Catálogo vacío" description="No hay modelos locales permitidos para administrar." /></ContentLayout>;
  return <ContentLayout title="Modelos locales" description="Selecciona, carga y descarga modelos instalados sin acceder a rutas ni realizar descargas."><Stack gap="lg">{notice ? <Alert variant="success" onDismiss={() => setNotice(null)}>{notice}</Alert> : null}{operationError ? <Alert variant="error">{modelErrorMessage(operationError)}</Alert> : null}{embedding ? <ModelCard title="Modelo de embeddings" model={embedding} runtimeState={center.embeddingStatus.data?.state ?? "unloaded"} busy={embeddingBusy} selectionDisabled={center.embeddingStatus.data?.state === "loaded"} unloadDisabled={center.semanticStatus.data?.state === "building"} onSelect={() => { center.select.reset(); setSelectionType("embedding"); }} onLoad={() => center.loadEmbedding.mutate()} onUnload={() => center.unloadEmbedding.mutate()} /> : <ErrorState title="Selección de embeddings inválida" message="El modelo activo no está disponible en el catálogo permitido." />}{llm ? <ModelCard title="Modelo generativo" model={llm} runtimeState={center.llmStatus.data?.state ?? "unloaded"} busy={llmBusy} selectionDisabled={center.llmStatus.data?.state === "loaded"} onSelect={() => { center.select.reset(); setSelectionType("llm"); }} onLoad={() => center.loadLlm.mutate()} onUnload={() => center.unloadLlm.mutate()} /> : <ErrorState title="Selección generativa inválida" message="El modelo activo no está disponible en el catálogo permitido." />}<SemanticIndexSummary status={center.semanticStatus.data} /><Text variant="caption">Activo identifica la próxima carga; cargado indica que el modelo se encuentra actualmente en memoria. Ninguna acción inicia una inferencia.</Text>{selectionType ? <ModelSelectionModal open modelType={selectionType} models={catalog.filter((model) => model.modelType === selectionType)} activeModelId={selectionType === "embedding" ? activeEmbeddingId : activeLlmId} pending={center.select.isPending} errorMessage={center.select.isError ? modelErrorMessage(center.select.error) : undefined} onOpenChange={(open) => { if (!open) setSelectionType(null); }} onConfirm={confirmSelection} /> : null}</Stack></ContentLayout>;
}
