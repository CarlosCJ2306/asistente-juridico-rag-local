import { Link } from "react-router-dom";

import { Card, Heading, Stack, Text } from "../../../design-system";
import type { PublicDocument } from "../types";
import styles from "../documents.module.css";
import { DocumentBadges } from "./DocumentBadges";
import { DocumentMetadata } from "./DocumentMetadata";
import { DocumentRagAvailability } from "./DocumentRagAvailability";

export function DocumentCard({ document }: { readonly document: PublicDocument }) {
  return (
    <Card className={styles.documentCard}>
      <Stack gap="md">
        <div className={styles.cardHeader}>
          <Heading as="h2" size="sm"><Link className={styles.titleLink} to={`/documents/${document.id}`}>{document.displayName}</Link></Heading>
          <DocumentBadges document={document} />
        </div>
        <DocumentRagAvailability document={document} />
        <DocumentMetadata document={document} />
        <Text variant="caption">Datos públicos del registro documental. El contenido y los archivos no se muestran en esta biblioteca.</Text>
        <div><Link className={styles.detailLink} to={`/documents/${document.id}`}>Ver detalle</Link></div>
      </Stack>
    </Card>
  );
}
