import { Badge, Card, Heading, Stack, Text } from "../../../design-system";
import type { LegalGraphProjection } from "../types";
import styles from "../legalNetwork.module.css";

function Count({ label, value }: { readonly label: string; readonly value: number }) {
  return <div className={styles.summaryItem}><Text variant="caption">{label}</Text><span className={styles.summaryValue}>{value}</span></div>;
}

export function LegalGraphSummary({ graph }: { readonly graph: LegalGraphProjection }) {
  return <Card as="section" padding="lg" className={styles.sectionCard}><Stack gap="md"><div className={styles.sectionHeader}><div><Heading as="h2">Resumen estructural de la red</Heading><Text variant="secondary">Medidas técnicas de conectividad; no determinan relevancia, causalidad ni conclusiones jurídicas.</Text></div><Badge variant={graph.matrix.validForReview ? "success" : "warning"}>{graph.matrix.validForReview ? "Estructura lista para revisión" : "Estructura con advertencias"}</Badge></div><div className={styles.summaryGrid}><Count label="Nodos" value={graph.summary.nodeCount} /><Count label="Relaciones" value={graph.summary.edgeCount} /><Count label="Nodos aislados" value={graph.summary.isolatedNodeCount} /><Count label="Componentes desconectados" value={graph.summary.disconnectedComponents} /><Count label="Advertencias estructurales" value={graph.summary.structuralWarningCount} /></div>{graph.summary.hasDirectedCycles ? <Text variant="secondary">La estructura contiene ciclos dirigidos; esta observación es únicamente técnica.</Text> : null}</Stack></Card>;
}
