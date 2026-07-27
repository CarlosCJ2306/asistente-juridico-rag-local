import { Badge, Stack, Text } from "../../../design-system";
import type { PublicDocument } from "../types";
import { ragAvailability } from "../utils";
import styles from "../documents.module.css";

export function DocumentRagAvailability({ document }: { readonly document: PublicDocument }) {
  const availability = ragAvailability(document.ragEligibilityReasons, document.ragEligible);
  return (
    <section className={styles.availability} aria-label="Disponibilidad para consultas">
      <Stack gap="sm">
        <Badge variant={availability.variant} role="status">{availability.label}</Badge>
        {availability.messages.length > 0 ? (
          <ul className={styles.reasonList}>
            {availability.messages.map((message) => <li key={message}><Text as="span" variant="secondary">{message}</Text></li>)}
          </ul>
        ) : <Text variant="secondary">Puede utilizarse como evidencia recuperada cuando corresponda.</Text>}
      </Stack>
    </section>
  );
}
