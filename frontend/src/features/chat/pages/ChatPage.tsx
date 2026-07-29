import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { isRequestCancelledError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { Alert, Button, Card, EmptyState, ErrorState, Inline, Stack, Text } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { useDocuments } from "../../documents";
import type { RagCitation, RagChatInput, RagChatResponse } from "../types";
import { useRagChat } from "../hooks";
import { chatErrorMessage } from "../utils";
import { ChatAnswer, ChatForm } from "../components";
import styles from "../chat.module.css";

interface VisibleResponse {
  readonly data: RagChatResponse;
  readonly completedAt: Date;
}

function citationCopyText(citation: RagCitation): string {
  const pages = citation.startPage === citation.endPage
    ? `página ${citation.startPage}`
    : `páginas ${citation.startPage}-${citation.endPage}`;
  return `${citation.displayName} · ${pages} · fragmento ${citation.chunkIndex}`;
}

export function ChatPage() {
  const documents = useDocuments(1, 100);
  const chat = useRagChat();
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const [visibleResponse, setVisibleResponse] = useState<VisibleResponse | null>(null);
  const [copyFeedback, setCopyFeedback] = useState("");
  const cancelled = isRequestCancelledError(chat.error);
  const error = chat.isError && !cancelled ? chatErrorMessage(chat.error) : null;

  function submit(input: RagChatInput) {
    setCopyFeedback("");
    chat.reset();
    chat.mutate(input, {
      onSuccess: (data) => setVisibleResponse({ data, completedAt: new Date() }),
    });
  }

  function newQuestion() {
    setVisibleResponse(null);
    chat.reset();
    questionRef.current?.focus();
  }

  function clearSession() {
    setVisibleResponse(null);
    setCopyFeedback("");
    chat.reset();
    questionRef.current?.focus();
  }

  async function copyText(value: string, feedback: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopyFeedback(feedback);
    } catch {
      setCopyFeedback("No fue posible copiar el contenido en este navegador.");
    }
  }

  const actions = (
    <Inline gap="sm" wrap>
      <Link className={styles.utilityLink} to="/documents">Gestionar documentos</Link>
      <Link className={styles.utilityLink} to="/documents/search">Búsqueda documental</Link>
    </Inline>
  );

  return (
    <ContentLayout title="Asistente jurídico" description="Consulta los documentos disponibles y recibe una respuesta sustentada en fuentes verificables." actions={actions}>
      <Stack gap="lg">
        <ProfessionalReviewNotice />
        <Card as="section" aria-labelledby="chat-question-title">
          <Stack gap="md">
            <div>
              <h2 className={styles.sectionTitle} id="chat-question-title">Formula una consulta</h2>
              <Text variant="secondary">Puedes usar todos los documentos elegibles o delimitar el corpus cuando lo necesites.</Text>
            </div>
            <ChatForm documents={documents.data?.items ?? []} pending={chat.isPending} canCancel={chat.canCancel} onSubmit={submit} onCancel={chat.cancel} inputRef={questionRef} />
            <Text variant="caption">Ejemplos: identifica el alcance de una disposición; resume los criterios documentados; compara evidencias disponibles. No se envían automáticamente.</Text>
          </Stack>
        </Card>
        <p className={styles.sessionNote}>Cada consulta se analiza de forma independiente.</p>
        {chat.isPending ? <Alert variant="info" aria-live="polite" title="Consultando evidencia y preparando la respuesta local…">El proceso puede preparar recursos locales bajo demanda. No se muestran fases ni porcentajes estimados.</Alert> : null}
        {cancelled ? <Alert variant="info" aria-live="polite" title="Consulta cancelada">La pregunta se conserva para que puedas volver a consultarla.</Alert> : null}
        {error ? <ErrorState title={error.title} message={error.message} retryAction={error.action === "models" ? <Link className={styles.utilityLink} to="/models">Administrar modelos</Link> : error.action === "documents" ? <Link className={styles.utilityLink} to="/documents#semantic-index">Administrar documentos</Link> : <Button variant="secondary" onClick={() => chat.reset()}>Cerrar aviso</Button>} /> : null}
        {visibleResponse ? <ChatAnswer response={visibleResponse.data} completedAt={visibleResponse.completedAt} onNewQuestion={newQuestion} onClear={clearSession} onCopyAnswer={() => void copyText(visibleResponse.data.answer, "Respuesta copiada.")} onCopyCitation={(citation) => void copyText(citationCopyText(citation), "Cita copiada.")} /> : null}
        {!visibleResponse && !chat.isPending && !error && !cancelled ? <EmptyState title="Listo para consultar" description="Escribe una pregunta para buscar evidencia local y recibir una respuesta con fuentes verificables." /> : null}
        <p className={styles.copyFeedback} aria-live="polite">{copyFeedback}</p>
      </Stack>
    </ContentLayout>
  );
}
