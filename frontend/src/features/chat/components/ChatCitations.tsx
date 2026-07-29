import { Link } from "react-router-dom";

import { Badge, Card, Heading, Inline, Stack, Text } from "../../../design-system";
import type { RagCitation } from "../types";
import { documentTypeLabel, knowledgeLayerLabel } from "../utils";
import styles from "../chat.module.css";

interface ChatCitationsProps {
  readonly citations: readonly RagCitation[];
  readonly onCopy: (citation: RagCitation) => void;
}

function pageLabel(citation: RagCitation): string {
  return citation.startPage === citation.endPage
    ? `Página ${citation.startPage}`
    : `Páginas ${citation.startPage}–${citation.endPage}`;
}

export function ChatCitations({ citations, onCopy }: ChatCitationsProps) {
  if (citations.length === 0) return null;
  return (
    <section aria-labelledby="chat-citations-title">
      <Stack gap="md">
        <div>
          <Heading as="h2" size="sm" id="chat-citations-title">Fuentes verificables</Heading>
          <Text variant="secondary">Estas referencias corresponden a la evidencia usada para la respuesta.</Text>
        </div>
        <ol className={styles.citationList}>
          {citations.map((citation) => (
            <li key={`${citation.documentId}-${citation.marker}`}>
              <Card as="article" padding="sm">
                <Stack gap="sm">
                  <Inline gap="sm" align="center"><Badge variant="info">{citation.marker}</Badge><Text variant="label">{citation.displayName}</Text></Inline>
                  <Text variant="secondary">{documentTypeLabel(citation.documentType)} · {knowledgeLayerLabel(citation.knowledgeLayer)} · {pageLabel(citation)} · Fragmento {citation.chunkIndex}</Text>
                  <Inline gap="sm" wrap>
                    <Link className={styles.documentLink} to={`/documents/${citation.documentId}`}>Abrir documento</Link>
                    <button type="button" className={styles.copyLink} onClick={() => onCopy(citation)}>Copiar cita</button>
                  </Inline>
                </Stack>
              </Card>
            </li>
          ))}
        </ol>
      </Stack>
    </section>
  );
}
