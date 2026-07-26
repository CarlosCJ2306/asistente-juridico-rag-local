import { Alert, Badge, Card, EmptyState, Heading, Stack, Text } from "../../../design-system";
import type { HpnValidationSummary } from "../types";
import styles from "../hpnMatrices.module.css";

function SummaryCount({ label, value }: { readonly label: string; readonly value: number }) {
  return <div className={styles.summaryItem}><Text variant="caption">{label}</Text><span className={styles.summaryValue}>{value}</span></div>;
}

export function HpnMatrixSummary({ summary }: { readonly summary: HpnValidationSummary }) {
  const hasStatusOrSourceAlerts = summary.draftNodeCount > 0
    || summary.rejectedNodeCount > 0
    || summary.draftRelationCount > 0
    || summary.staleSourceCount > 0
    || summary.unavailableSourceCount > 0
    || summary.evidenceWithoutValidSourceCount > 0
    || summary.normWithoutValidSourceCount > 0;

  return (
    <Card as="section" padding="lg" className={styles.sectionCard}>
      <Stack gap="md">
        <div className={styles.sectionHeader}>
          <div>
            <Heading as="h2">Resumen estructural</Heading>
            <Text variant="secondary">Conteos técnicos devueltos por el backend para apoyar la revisión manual; no califican suficiencia, prueba ni aplicabilidad.</Text>
          </div>
          <Badge variant={summary.validForReview ? "success" : "warning"}>{summary.validForReview ? "Estructura lista para revisión" : "Estructura pendiente"}</Badge>
        </div>
        <div className={styles.summaryGrid}>
          <SummaryCount label="Hechos" value={summary.factCount} />
          <SummaryCount label="Evidencias" value={summary.evidenceCount} />
          <SummaryCount label="Normas" value={summary.normCount} />
          <SummaryCount label="Relaciones" value={summary.relationCount} />
          <SummaryCount label="Nodos en borrador" value={summary.draftNodeCount} />
          <SummaryCount label="Nodos rechazados" value={summary.rejectedNodeCount} />
          <SummaryCount label="Relaciones en borrador" value={summary.draftRelationCount} />
          <SummaryCount label="Fuentes desactualizadas" value={summary.staleSourceCount} />
          <SummaryCount label="Fuentes no disponibles" value={summary.unavailableSourceCount} />
          <SummaryCount label="Evidencias sin fuente válida" value={summary.evidenceWithoutValidSourceCount} />
          <SummaryCount label="Normas sin fuente válida" value={summary.normWithoutValidSourceCount} />
        </div>
        {hasStatusOrSourceAlerts
          ? <Alert variant="warning" title="Revisión estructural pendiente"><Text>Uno o más contadores de estado o fuentes requieren atención profesional. Cada categoría se presenta por separado para evitar dobles conteos.</Text></Alert>
          : <EmptyState title="Sin alertas de estado o fuentes" description="Los contadores de borradores, rechazos y advertencias de fuentes son cero. Esto no constituye una conclusión jurídica." />}
      </Stack>
    </Card>
  );
}
