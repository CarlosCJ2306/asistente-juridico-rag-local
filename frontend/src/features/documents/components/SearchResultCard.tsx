import { Link } from "react-router-dom";

import { Card, Heading, Stack, Text } from "../../../design-system";
import type { HybridSearchItem } from "../types";
import { DOCUMENT_TYPE_LABELS, KNOWLEDGE_LAYER_LABELS } from "../utils";

export function SearchResultCard({ item }: { readonly item: HybridSearchItem }) {
  return (
    <Card>
      <Stack gap="sm">
        <Heading as="h2" size="sm">{item.documentName}</Heading>
        <Text variant="secondary">
          {DOCUMENT_TYPE_LABELS[item.documentType]} · {KNOWLEDGE_LAYER_LABELS[item.knowledgeLayer].label} · páginas {item.startPage}-{item.endPage} · fragmento {item.chunkIndex}
        </Text>
        <Text>{item.snippet}</Text>
        <Text variant="label">Relevancia combinada: {item.hybridScore.toFixed(4)}</Text>
        <Text variant="caption">Rango textual {item.textRank ?? "—"} · rango semántico {item.semanticRank ?? "—"}</Text>
        <Link to={`/documents/${item.documentId}`}>Abrir documento</Link>
      </Stack>
    </Card>
  );
}
