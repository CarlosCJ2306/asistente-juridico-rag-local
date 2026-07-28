import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { toAppError } from "../../../api";
import { Button, Card, EmptyState, ErrorState, FormField, Select, Stack, TextInput } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { getEmbeddingStatus, getSemanticStatus } from "../api/semanticIndex.api";
import { CorpusSelector, SearchResultCard, SearchStatusBanner } from "../components";
import { useDocuments, useHybridSearch } from "../hooks";
import type { HybridSearchInput, TextMatchMode } from "../types";

const DEFAULT_TOP_K = 10;

export function DocumentSearchPage() {
  const [query, setQuery] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [knowledgeLayer, setKnowledgeLayer] = useState("");
  const [matchMode, setMatchMode] = useState<TextMatchMode>("all_terms");
  const [minPage, setMinPage] = useState("");
  const [maxPage, setMaxPage] = useState("");
  const documents = useDocuments(1, 100);
  const embeddingStatus = useQuery({ queryKey: ["semantic-index", "model"], queryFn: ({ signal }) => getEmbeddingStatus(signal) });
  const semanticStatus = useQuery({ queryKey: ["semantic-index", "status"], queryFn: ({ signal }) => getSemanticStatus(signal) });
  const search = useHybridSearch();
  const ready = semanticStatus.data?.state === "ready" && !semanticStatus.data.needsRebuild;
  const pageRangeInvalid = Boolean(minPage && maxPage && Number(minPage) > Number(maxPage));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery || pageRangeInvalid) return;
    const input: HybridSearchInput = {
      query: normalizedQuery, textMatchMode: matchMode, topK: DEFAULT_TOP_K,
      documentId: documentId || undefined, documentTypes: documentType ? [documentType] : undefined,
      knowledgeLayers: knowledgeLayer ? [knowledgeLayer] : undefined,
      minPage: minPage ? Number(minPage) : undefined, maxPage: maxPage ? Number(maxPage) : undefined,
    };
    search.mutate(input);
  }

  const pendingLabel = embeddingStatus.data?.state === "loaded" ? "Buscando…" : "Preparando modelo local…";
  return (
    <ContentLayout title="Búsqueda documental" description="Recuperación híbrida local y gobernada antes del Chat jurídico." actions={<Link to="/documents">Volver a documentos</Link>}>
      <Stack gap="lg">
        <Card as="section">
          <form onSubmit={submit}>
            <Stack gap="md">
              <FormField label="Consulta" required>{(props) => <TextInput {...props} value={query} maxLength={500} onChange={(event) => setQuery(event.target.value)} />}</FormField>
              <CorpusSelector documents={documents.data?.items ?? []} documentId={documentId} documentType={documentType} knowledgeLayer={knowledgeLayer} onDocumentIdChange={setDocumentId} onDocumentTypeChange={setDocumentType} onKnowledgeLayerChange={setKnowledgeLayer} />
              <FormField label="Modo de coincidencia">{(props) => <Select {...props} value={matchMode} onChange={(event) => setMatchMode(event.target.value as TextMatchMode)}><option value="all_terms">Todos los términos</option><option value="any_term">Cualquier término</option><option value="phrase">Frase exacta</option></Select>}</FormField>
              <FormField label="Página mínima">{(props) => <TextInput {...props} type="number" min="1" value={minPage} onChange={(event) => setMinPage(event.target.value)} />}</FormField>
              <FormField label="Página máxima" error={pageRangeInvalid ? "La página máxima no puede ser menor que la mínima." : undefined}>{(props) => <TextInput {...props} type="number" min="1" value={maxPage} onChange={(event) => setMaxPage(event.target.value)} />}</FormField>
              <SearchStatusBanner embeddingLoaded={embeddingStatus.data?.state === "loaded"} semanticReady={semanticStatus.data?.state === "ready"} needsRebuild={semanticStatus.data?.needsRebuild ?? false} />
              <Button type="submit" loading={search.isPending} disabled={!ready || !query.trim() || pageRangeInvalid}>{search.isPending ? pendingLabel : "Buscar"}</Button>
            </Stack>
          </form>
        </Card>
        {search.isError ? <ErrorState title="Búsqueda no disponible" message={toAppError(search.error).userMessage} /> : null}
        {search.data?.items.length === 0 ? <EmptyState title="Sin resultados" description="No se encontró evidencia documental elegible para esta consulta." /> : null}
        {search.data?.items.length ? <ul>{search.data.items.map((item) => <li key={item.chunkId}><SearchResultCard item={item} /></li>)}</ul> : null}
      </Stack>
    </ContentLayout>
  );
}
