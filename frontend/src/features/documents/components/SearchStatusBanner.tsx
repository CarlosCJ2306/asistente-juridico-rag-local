import { Link } from "react-router-dom";

import { Alert } from "../../../design-system";

interface SearchStatusBannerProps {
  readonly embeddingLoaded: boolean;
  readonly semanticReady: boolean;
  readonly needsRebuild: boolean;
}

export function SearchStatusBanner({ embeddingLoaded, semanticReady, needsRebuild }: SearchStatusBannerProps) {
  if (embeddingLoaded && semanticReady && !needsRebuild) return <Alert variant="success">Embeddings e índice disponibles.</Alert>;
  if (!embeddingLoaded && semanticReady && !needsRebuild) return <Alert variant="info" title="Carga bajo demanda" action={<Link to="/models">Administrar modelos</Link>}>El modelo local se preparará automáticamente al buscar.</Alert>;
  if (needsRebuild) return <Alert variant="warning" title="Índice incompatible" action={<Link to="/documents#semantic-index">Administrar índice</Link>}>El índice semántico requiere reconstrucción antes de buscar.</Alert>;
  return <Alert variant="warning" title="Índice no disponible" action={<Link to="/documents#semantic-index">Administrar índice</Link>}>El índice semántico todavía no está disponible para esta búsqueda.</Alert>;
}
