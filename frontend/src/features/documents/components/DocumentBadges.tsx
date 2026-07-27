import { Badge, Cluster } from "../../../design-system";
import type { PublicDocument } from "../types";
import {
  DOCUMENT_STATUS_LABELS,
  INDEX_STATUS_LABELS,
  KNOWLEDGE_LAYER_LABELS,
  LEGAL_VALIDITY_LABELS,
  REVIEW_STATUS_LABELS,
} from "../utils";

export function DocumentBadges({ document }: { readonly document: PublicDocument }) {
  const layer = KNOWLEDGE_LAYER_LABELS[document.knowledgeLayer];
  const technical = DOCUMENT_STATUS_LABELS[document.status];
  const review = REVIEW_STATUS_LABELS[document.reviewStatus];
  const validity = LEGAL_VALIDITY_LABELS[document.legalValidityStatus];
  const indexing = INDEX_STATUS_LABELS[document.indexStatus];
  return (
    <Cluster gap="sm" className="document-badges">
      <Badge variant={layer.variant}>{layer.label}</Badge>
      <Badge variant={technical.variant}>{technical.label}</Badge>
      <Badge variant={review.variant}>{review.label}</Badge>
      <Badge variant={validity.variant}>{validity.label}</Badge>
      <Badge variant={indexing.variant}>{indexing.label}</Badge>
    </Cluster>
  );
}
