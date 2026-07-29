import { useEffect, useRef } from "react";

import { Alert, Badge, Button, Card, Heading, Inline, Stack, Text } from "../../../design-system";
import { ProfessionalReviewNotice } from "../../../components";
import type { RagChatResponse } from "../types";
import { formatLocalTime } from "../utils";
import { ChatCitations } from "./ChatCitations";
import styles from "../chat.module.css";

interface ChatAnswerProps {
  readonly response: RagChatResponse;
  readonly completedAt: Date;
  readonly onNewQuestion: () => void;
  readonly onClear: () => void;
  readonly onCopyAnswer: () => void;
  readonly onCopyCitation: (citation: RagChatResponse["citations"][number]) => void;
}

export function ChatAnswer({ response, completedAt, onNewQuestion, onClear, onCopyAnswer, onCopyCitation }: ChatAnswerProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [response]);

  if (response.status === "insufficient_context") {
    return (
      <Card as="section" aria-labelledby="chat-result-title">
        <Stack gap="md">
          <div ref={headingRef} tabIndex={-1} className={styles.focusTarget}><Heading as="h2" size="md" id="chat-result-title">Evidencia insuficiente</Heading></div>
          <Alert variant="info" title="No se encontró evidencia documental suficiente para responder esta pregunta.">
            Prueba reformulando la consulta, ampliando el corpus o incorporando una fuente pertinente. Qwen no generó una respuesta sin evidencia documental elegible.
          </Alert>
          <Inline gap="sm" wrap>
            <Button onClick={onNewQuestion}>Reformular pregunta</Button>
            <Button variant="secondary" onClick={onClear}>Limpiar sesión</Button>
          </Inline>
        </Stack>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <Card as="section" aria-labelledby="chat-result-title">
        <Stack gap="md">
          <div className={styles.answerHeader}>
            <div>
              <div ref={headingRef} tabIndex={-1} className={styles.focusTarget}><Heading as="h2" size="md" id="chat-result-title">Respuesta sustentada</Heading></div>
              <Text variant="secondary">Consulta independiente · {formatLocalTime(completedAt)}</Text>
            </div>
            <Badge variant="success">{`${response.citationCount} ${response.citationCount === 1 ? "fuente" : "fuentes"}`}</Badge>
          </div>
          <Text className={styles.answerText}>{response.answer}</Text>
          <Inline gap="sm" wrap>
            <Button variant="secondary" onClick={onCopyAnswer}>Copiar respuesta</Button>
            <Button onClick={onNewQuestion}>Nueva consulta</Button>
            <Button variant="ghost" onClick={onClear}>Limpiar sesión</Button>
          </Inline>
        </Stack>
      </Card>
      <ProfessionalReviewNotice />
      <ChatCitations citations={response.citations} onCopy={onCopyCitation} />
    </Stack>
  );
}
