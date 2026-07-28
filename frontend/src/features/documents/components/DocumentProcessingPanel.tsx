import { Card, Heading, Stack, Text } from "../../../design-system";
import { useDocumentProcessing } from "../hooks/useDocumentProcessing";
import styles from "../documents.module.css";

export function DocumentProcessingPanel() {
  const query = useDocumentProcessing();
  const summary = query.data;
  return <Card as="section" aria-labelledby="automatic-processing-title"><Stack gap="md"><div><Heading id="automatic-processing-title" as="h2" size="sm">Procesamiento automático</Heading><Text variant="secondary">Los PDF recibidos se registran, extraen e indexan localmente mediante una cola persistente.</Text></div>{summary ? <div className={styles.summaryGrid}><div className={styles.summaryItem}><Text variant="caption">En cola</Text><span className={styles.summaryValue}>{summary.queued}</span></div><div className={styles.summaryItem}><Text variant="caption">Procesando</Text><span className={styles.summaryValue}>{summary.processing}</span></div><div className={styles.summaryItem}><Text variant="caption">Completados</Text><span className={styles.summaryValue}>{summary.completedRecently}</span></div><div className={styles.summaryItem}><Text variant="caption">Fallidos o en cuarentena</Text><span className={styles.summaryValue}>{summary.failed + summary.quarantined}</span></div></div> : <Text variant="secondary" aria-live="polite">{query.isError ? "Estado automático no disponible." : "Consultando la cola local…"}</Text>}</Stack></Card>;
}
