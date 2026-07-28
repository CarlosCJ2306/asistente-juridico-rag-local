import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, Heading, Inline, Modal, Stack, Text } from "../../../design-system";
import { useNotifications } from "../../../hooks/useNotifications";
import { getEmbeddingStatus, getSemanticStatus, loadEmbeddings, rebuildSemanticIndex, semanticIndexKeys, unloadEmbeddings } from "../api/semanticIndex.api";

export function SemanticIndexPanel() {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  const [confirm, setConfirm] = useState(false);
  const model = useQuery({ queryKey: semanticIndexKeys.model, queryFn: ({ signal }) => getEmbeddingStatus(signal) });
  const index = useQuery({ queryKey: semanticIndexKeys.status, queryFn: ({ signal }) => getSemanticStatus(signal) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: semanticIndexKeys.all });
  const load = useMutation({ mutationFn: loadEmbeddings, onSuccess: refresh });
  const unload = useMutation({ mutationFn: unloadEmbeddings, onSuccess: refresh });
  const rebuild = useMutation({ mutationFn: rebuildSemanticIndex, onSuccess: () => { refresh(); void queryClient.invalidateQueries({ queryKey: ["documents"] }); notify({ kind: "success", title: "Índice semántico reconstruido", message: "La disponibilidad documental se actualizó según la política local.", deduplicationKey: "semantic-rebuild" }); } });
  const busy = load.isPending || unload.isPending || rebuild.isPending;
  const dismissPolicy = rebuild.isPending ? { preventClose: true as const, preventCloseReason: "La reconstrucción está en curso." } : { preventClose: false as const };
  return <Card as="section" id="semantic-index"><Stack gap="md"><div><Heading as="h2" size="sm">Índice semántico</Heading><Text variant="secondary">Proyección global reconstruible: procesa todos los documentos elegibles según SQLite. No carga Qwen ni usa internet.</Text></div><Text variant="secondary">Modelo: {model.data?.state ?? "consultando"} · Índice: {index.data?.state ?? "consultando"} · Chunks: {index.data?.indexedChunks ?? 0}/{index.data?.activeChunks ?? 0}{index.data?.needsRebuild ? " · Requiere reconstrucción" : ""}</Text><Inline gap="sm"><Button variant="secondary" loading={load.isPending} disabled={busy || model.data?.state === "loaded"} onClick={() => load.mutate()}>Cargar embeddings</Button><Button variant="ghost" loading={unload.isPending} disabled={busy || model.data?.state !== "loaded"} onClick={() => unload.mutate()}>Descargar embeddings</Button><Button disabled={busy || model.data?.state !== "loaded"} onClick={() => setConfirm(true)}>Reconstruir índice semántico</Button></Inline><Modal open={confirm} onOpenChange={setConfirm} title="Reconstruir índice semántico" description="Operación global y local; puede tardar." {...dismissPolicy}><Stack gap="md"><Text variant="secondary">Usa embeddings locales y reconstruye ChromaDB como proyección. Solo incorpora documentos elegibles; no elimina PDF ni chunks y no usa Qwen.</Text><Inline gap="sm" justify="end"><Button variant="ghost" disabled={rebuild.isPending} onClick={() => setConfirm(false)}>Cancelar</Button><Button loading={rebuild.isPending} onClick={() => rebuild.mutate()}>Iniciar reconstrucción</Button></Inline></Stack></Modal></Stack></Card>;
}
