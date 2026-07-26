import { Alert, Badge, Card, EmptyState, Heading, Stack, Text } from "../../../design-system";
import type { LegalGraphProjection, LegalGraphWarningCode } from "../types";
import styles from "../legalNetwork.module.css";

const NODE_TYPE_LABELS = { fact: "Hecho", evidence: "Evidencia", norm: "Norma" } as const;
const REVIEW_LABELS = { draft: "Borrador", reviewed: "Revisado", rejected: "Rechazado" } as const;
const WARNING_LABELS: Readonly<Record<LegalGraphWarningCode, string>> = {
  GRAPH_EMPTY: "La red no contiene elementos.",
  GRAPH_DISCONNECTED_COMPONENTS: "La red presenta componentes desconectados.",
  GRAPH_DIRECTED_CYCLE_DETECTED: "La red presenta ciclos dirigidos.",
  GRAPH_MATRIX_ARCHIVED: "La matriz está archivada y se presenta en modo de solo lectura.",
  GRAPH_REVIEW_DRAFT: "Existen elementos pendientes de revisión.",
  GRAPH_REVIEW_REJECTED: "Existen elementos rechazados.",
  GRAPH_SOURCE_STALE: "Existen fuentes desactualizadas.",
  GRAPH_SOURCE_UNAVAILABLE: "Existen fuentes no disponibles.",
};

export function LegalGraphTextualView({ graph }: { readonly graph: LegalGraphProjection }) {
  const labels = new Map(graph.nodes.map((node) => [node.id, node.label] as const));
  if (graph.nodes.length === 0) return <EmptyState title="Red sin elementos" description="La matriz no tiene nodos para representar. Esto no modifica la matriz ni sus estados." />;
  return <Card as="section" padding="lg" className={styles.sectionCard}><Stack gap="lg"><div><Heading as="h2">Alternativa textual de la red</Heading><Text variant="secondary">Representación accesible y obligatoria de los mismos nodos y relaciones mostrados visualmente.</Text></div>{graph.warnings.length ? <Stack gap="sm">{graph.warnings.map((warning, index) => <Alert key={`${warning.code}-${warning.entityType}-${index}`} variant={warning.severity === "warning" ? "warning" : "info"} title="Advertencia estructural"><Text>{WARNING_LABELS[warning.code]}</Text></Alert>)}</Stack> : null}<div><Heading as="h3" size="sm">Nodos</Heading><ul className={styles.textList}>{graph.nodes.map((node) => <li key={node.id} className={styles.textItem}><Stack gap="sm"><div className={styles.itemHeader}><div><Badge variant="info">{NODE_TYPE_LABELS[node.type]}</Badge><Heading as="h4" size="sm">{node.label}</Heading></div><Badge variant={node.reviewStatus === "rejected" ? "danger" : node.reviewStatus === "reviewed" ? "success" : "neutral"}>{REVIEW_LABELS[node.reviewStatus]}</Badge></div><Text variant="secondary">Orden de presentación: {node.displayOrder}. Fuentes: {node.sourceSummary.total}; desactualizadas: {node.sourceSummary.stale}; no disponibles: {node.sourceSummary.unavailable}.</Text></Stack></li>)}</ul></div><div><Heading as="h3" size="sm">Relaciones dirigidas</Heading>{graph.edges.length ? <ul className={styles.textList}>{graph.edges.map((edge) => <li key={edge.id} className={styles.textItem}><Stack gap="sm"><Heading as="h4" size="sm">{edge.label}</Heading><Text variant="secondary">Origen: {labels.get(edge.source) ?? "Elemento no disponible"}. Destino: {labels.get(edge.target) ?? "Elemento no disponible"}.</Text><Text variant="caption">Estado de revisión: {REVIEW_LABELS[edge.reviewStatus]}.</Text></Stack></li>)}</ul> : <Text variant="secondary">No hay relaciones dirigidas registradas.</Text>}</div></Stack></Card>;
}
