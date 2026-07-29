import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, Card, Heading, Inline, Stack, Text } from "../../../design-system";
import type { ConversationCitation, ConversationMessage } from "../types";
import styles from "../chat.module.css";

function coverage(value: ConversationMessage["coverageStatus"]): string { return value === "full" ? "Respuesta sustentada" : value === "partial" ? "Respuesta parcialmente sustentada" : "Evidencia insuficiente"; }
function citationText(citation: ConversationCitation): string { return `${citation.marker} ${citation.displayName}\n${citation.documentType} · ${citation.knowledgeLayer}\nPágina ${citation.startPage}${citation.endPage !== citation.startPage ? `–${citation.endPage}` : ""} · Fragmento ${citation.chunkIndex}\n“${citation.directQuote}”`; }

interface ConversationEvidenceProps { readonly message: ConversationMessage | undefined; readonly selected: string | undefined; }
export function ConversationEvidence({ message, selected }: ConversationEvidenceProps) {
  const selectedHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (selected) selectedHeading.current?.focus(); }, [selected]);
  if (!message) return null;
  return <section className={styles.evidenceContent} aria-labelledby="evidence-title"><Stack gap="md"><header><Heading as="h2" size="md" id="evidence-title">Evidencia de esta respuesta</Heading><Text variant="secondary">{message.coverageStatus ? coverage(message.coverageStatus) : "Respuesta"} · Snapshot histórico de las fuentes utilizadas.</Text></header><Inline gap="sm" wrap><Badge variant="neutral">{`${message.claims.length} conclusiones`}</Badge><Badge variant="neutral">{`${message.citations.length} citas`}</Badge></Inline>{message.citations.map((citation) => <Card key={citation.id} as="article" className={selected === citation.id ? styles.selectedCitation : undefined}><Stack gap="sm"><h3 ref={selected === citation.id ? selectedHeading : undefined} tabIndex={-1} className={styles.citationHeading}>{citation.marker} · {citation.displayName}</h3><Text variant="secondary">{citation.documentType} · {citation.knowledgeLayer} · Página {citation.startPage}{citation.endPage !== citation.startPage ? `–${citation.endPage}` : ""}</Text>{citation.issuingEntity ? <Text variant="secondary">{citation.issuingEntity}</Text> : null}{citation.documentDate ? <Text variant="secondary">Fecha documental: {new Date(citation.documentDate).toLocaleDateString()}</Text> : null}{citation.locatorLabel ? <Text variant="secondary">{citation.locatorLabel}</Text> : null}<div><Text variant="secondary">Cita textual{citation.quoteTruncated ? " (recortada)" : ""}</Text><blockquote className={styles.quote}>{citation.directQuote}</blockquote></div><Inline gap="sm" wrap>{citation.documentAvailable ? <Link className={styles.utilityLink} to={`/documents/${citation.documentId}`}>Abrir documento</Link> : <Text variant="secondary">Documento no disponible actualmente</Text>}<Button variant="ghost" onClick={() => void navigator.clipboard.writeText(citationText(citation))}>Copiar cita</Button></Inline></Stack></Card>)}{message.claims.length > 0 ? <div><Heading as="h3" size="sm">Conclusiones sustentadas</Heading><ol className={styles.claimList}>{message.claims.map((claim) => <li key={claim.id}>{claim.statement}</li>)}</ol></div> : null}</Stack></section>;
}
