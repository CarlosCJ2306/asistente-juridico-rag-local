import { useMemo } from "react";
import { Link } from "react-router-dom";

import { Alert, Badge, Button, Heading, Inline, Stack, Text } from "../../../design-system";
import type { ConversationCitation, ConversationMessage } from "../types";
import styles from "../chat.module.css";

function coverage(value: ConversationMessage["coverageStatus"]): string { return value === "full" ? "Respuesta sustentada" : value === "partial" ? "Respuesta parcialmente sustentada" : "Evidencia insuficiente"; }
function messageTime(value: string): string { return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function contentParts(content: string, citations: readonly ConversationCitation[], onCitation: (citation: ConversationCitation, trigger: HTMLElement) => void) {
  const available = new Map(citations.map((citation) => [citation.marker, citation]));
  return content.split(/(\[F[1-9]\d*\])/gu).map((part, index) => {
    const citation = available.get(part);
    return citation ? <button key={`${part}-${index}`} type="button" className={styles.marker} onClick={(event) => onCitation(citation, event.currentTarget)} aria-label={`Ver evidencia ${citation.marker}, ${citation.displayName}, página ${citation.startPage}`}>{part}</button> : part;
  });
}

interface ConversationThreadProps {
  readonly messages: readonly ConversationMessage[];
  readonly pending: boolean;
  readonly onCitation: (message: ConversationMessage, citation: ConversationCitation, trigger: HTMLElement) => void;
  readonly onEvidence: (message: ConversationMessage, trigger: HTMLElement) => void;
  readonly onCopy: (message: ConversationMessage) => void;
  readonly onExample: (value: string) => void;
}

export function ConversationThread({ messages, pending, onCitation, onEvidence, onCopy, onExample }: ConversationThreadProps) {
  const ordered = useMemo(() => [...messages].sort((left, right) => left.sequenceNumber - right.sequenceNumber), [messages]);
  if (ordered.length === 0) return <section className={styles.emptyConversation} aria-labelledby="conversation-thread-title"><div><Heading as="h2" size="lg" id="conversation-thread-title">¿En qué podemos ayudarte?</Heading><Text variant="secondary">Realiza una consulta y el asistente buscará evidencia en los documentos disponibles.</Text></div><Inline gap="sm" wrap><Button variant="ghost" onClick={() => onExample("¿Cuál es el alcance de la evidencia disponible?")}>Explorar evidencia</Button><Button variant="ghost" onClick={() => onExample("¿Qué documentos pueden respaldar esta consulta?")}>Revisar documentos</Button></Inline></section>;

  return <section className={styles.thread} aria-label="Mensajes de la conversación"><ol className={styles.messageList}>{ordered.map((message) => <li key={message.id} className={message.role === "user" ? styles.userMessageRow : styles.assistantMessageRow}>{message.role === "user" ? <article className={styles.userMessage} aria-label="Tu consulta"><Text className={styles.answerText}>{message.content}</Text><Text variant="secondary" className={styles.messageTime}>{messageTime(message.createdAt)}</Text></article> : message.coverageStatus === "insufficient" ? <article className={styles.insufficientMessage} aria-label="Respuesta del asistente"><Stack gap="sm"><Heading as="h2" size="sm">Evidencia insuficiente</Heading><Text>No se encontró respaldo documental suficiente para responder.</Text><Inline gap="sm" wrap><Button variant="ghost" onClick={() => onExample("Escribe una consulta más específica: ")}>Reformular</Button><Link className={styles.utilityLink} to="/documents">Gestionar documentos</Link><Link className={styles.utilityLink} to="/documents/search">Búsqueda documental</Link></Inline></Stack></article> : <article className={styles.assistantMessage} aria-label="Respuesta del asistente"><Stack gap="sm"><Text className={styles.answerText}>{contentParts(message.content, message.citations, (citation, trigger) => onCitation(message, citation, trigger))}</Text><Inline gap="sm" wrap><Badge variant={message.coverageStatus === "full" ? "success" : "neutral"}>{coverage(message.coverageStatus)}</Badge><Text variant="secondary" className={styles.messageTime}>{messageTime(message.createdAt)}</Text></Inline>{message.claims.length > 0 ? <div><Heading as="h3" size="sm">Conclusiones sustentadas</Heading><ol className={styles.claimList}>{message.claims.map((claim) => <li key={claim.id}>{claim.statement} {claim.citationIds.map((citationId) => { const citation = message.citations.find((item) => item.id === citationId); return citation ? <button key={citationId} type="button" className={styles.marker} onClick={(event) => onCitation(message, citation, event.currentTarget)}>{citation.marker}</button> : null; })}</li>)}</ol></div> : null}{message.coverageStatus === "partial" && message.unsupportedPoints.length > 0 ? <Alert variant="warning" title="Puntos no verificados">{message.unsupportedPoints.join(" ")}</Alert> : null}<Inline gap="sm" wrap><Button variant="ghost" onClick={() => onCopy(message)}>Copiar respuesta</Button>{message.citations.length > 0 ? <Button variant="ghost" onClick={(event) => onEvidence(message, event.currentTarget)}>{`Ver evidencias · ${message.citations.length}`}</Button> : null}</Inline></Stack></article>}</li>)}</ol>{pending ? <div className={styles.pendingMessage} aria-live="polite"><Text>Consultando evidencia y preparando una respuesta local…</Text></div> : null}</section>;
}
