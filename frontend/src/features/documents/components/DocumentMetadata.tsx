import { Text } from "../../../design-system";
import type { PublicDocument } from "../types";
import { DOCUMENT_TYPE_LABELS, formatDocumentDate, formatDocumentSize, SOURCE_KIND_LABELS } from "../utils";
import styles from "../documents.module.css";

interface MetadataItem {
  readonly label: string;
  readonly value: string;
}

function values(document: PublicDocument): readonly MetadataItem[] {
  const items: MetadataItem[] = [
    { label: "Tipo", value: DOCUMENT_TYPE_LABELS[document.documentType] },
    { label: "Procedencia", value: SOURCE_KIND_LABELS[document.sourceKind] },
    { label: "Tamaño", value: formatDocumentSize(document.sizeBytes) },
    { label: "Actualizado", value: formatDocumentDate(document.updatedAt) },
  ];
  if (document.issuingEntity) items.push({ label: "Entidad emisora", value: document.issuingEntity });
  if (document.jurisdiction) items.push({ label: "Jurisdicción", value: document.jurisdiction });
  if (document.legalArea) items.push({ label: "Área jurídica", value: document.legalArea });
  if (document.versionLabel) items.push({ label: "Versión", value: document.versionLabel });
  if (document.publishedAt) items.push({ label: "Publicación", value: formatDocumentDate(document.publishedAt) });
  if (document.expiresAt) items.push({ label: "Expiración", value: formatDocumentDate(document.expiresAt) });
  if (document.isExpired) items.push({ label: "Estado de expiración", value: "Expirado" });
  return items;
}

export function DocumentMetadata({ document, detailed = false }: { readonly document: PublicDocument; readonly detailed?: boolean }) {
  const items = values(document);
  const visibleItems = detailed ? items : items.slice(0, 6);
  return (
    <dl className={styles.metadataGrid}>
      {visibleItems.map((item) => (
        <div key={item.label} className={styles.metadataItem}>
          <dt><Text as="span" variant="caption">{item.label}</Text></dt>
          <dd className={styles.metadataValue}><Text as="span">{item.value}</Text></dd>
        </div>
      ))}
    </dl>
  );
}
