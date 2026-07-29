import { Link } from "react-router-dom";

import { Alert, Card, Heading, Stack, Text } from "../../../design-system";
import type { SemanticStatus } from "../../documents";

export function SemanticIndexSummary({ status }: { readonly status?: SemanticStatus }) {
  const requiresRebuild = status?.needsRebuild ?? false;
  return <Card as="section"><Stack gap="sm"><Heading as="h2" size="sm">Índice semántico</Heading><Text variant="secondary">Estado: {status?.state ?? "consultando"} · Chunks: {status?.indexedChunks ?? 0}/{status?.activeChunks ?? 0}</Text>{requiresRebuild ? <Alert variant="warning" title="Requiere reconstrucción">El embedding activo no es compatible con el índice actual o cambió la fuente documental. La reconstrucción siempre es explícita.</Alert> : null}<Link to="/documents#semantic-index">Administrar índice semántico</Link></Stack></Card>;
}
