import { useState, type FormEvent, type KeyboardEvent, type RefObject } from "react";

import { Button, FormField, Inline, Select, Stack, Textarea, TextInput } from "../../../design-system";
import { CorpusSelector } from "../../documents";
import type { DocumentType, KnowledgeLayer, PublicDocument } from "../../documents";
import type { RagChatInput } from "../types";
import styles from "../chat.module.css";

const MAX_QUESTION_LENGTH = 500;
const TOP_K_VALUES = [4, 8, 12, 20] as const;

function positiveInteger(value: string): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 ? parsed : undefined;
}

interface ChatFormProps {
  readonly documents: readonly PublicDocument[];
  readonly pending: boolean;
  readonly canCancel: boolean;
  readonly onSubmit: (input: RagChatInput) => void;
  readonly onCancel: () => void;
  readonly inputRef: RefObject<HTMLTextAreaElement>;
}

export function ChatForm({ documents, pending, canCancel, onSubmit, onCancel, inputRef }: ChatFormProps) {
  const [question, setQuestion] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [documentId, setDocumentId] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [knowledgeLayer, setKnowledgeLayer] = useState("");
  const [textMatchMode, setTextMatchMode] = useState<RagChatInput["textMatchMode"]>("all_terms");
  const [topK, setTopK] = useState(8);
  const [minPage, setMinPage] = useState("");
  const [maxPage, setMaxPage] = useState("");
  const normalizedQuestion = question.trim();
  const parsedMinPage = positiveInteger(minPage);
  const parsedMaxPage = positiveInteger(maxPage);
  const pageFormatInvalid = Boolean((minPage && parsedMinPage === undefined) || (maxPage && parsedMaxPage === undefined));
  const pageRangeInvalid = Boolean(parsedMinPage && parsedMaxPage && parsedMinPage > parsedMaxPage);
  const questionError = question.length > MAX_QUESTION_LENGTH ? `La pregunta no puede superar ${MAX_QUESTION_LENGTH} caracteres.` : undefined;
  const disabled = pending || !normalizedQuestion || Boolean(questionError) || pageFormatInvalid || pageRangeInvalid;

  function buildInput(): RagChatInput | null {
    if (disabled) return null;
    return {
      question: normalizedQuestion,
      textMatchMode,
      topK,
      documentId: documentId || undefined,
      documentTypes: documentType ? [documentType as DocumentType] : undefined,
      knowledgeLayers: knowledgeLayer ? [knowledgeLayer as KnowledgeLayer] : undefined,
      minPage: parsedMinPage,
      maxPage: parsedMaxPage,
    };
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = buildInput();
    if (input) onSubmit(input);
  }

  function onQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    const input = buildInput();
    if (input) onSubmit(input);
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stack gap="md">
        <FormField label="Pregunta jurídica" required description="Describe la consulta. Cada pregunta se analiza de forma independiente." error={questionError} counter={`${question.length}/${MAX_QUESTION_LENGTH} caracteres`}>
          {(props) => <Textarea {...props} ref={inputRef} value={question} maxLength={MAX_QUESTION_LENGTH + 1} placeholder="Escribe una pregunta sobre los documentos disponibles" onChange={(event) => setQuestion(event.target.value)} onKeyDown={onQuestionKeyDown} disabled={pending} />}
        </FormField>
        <Button type="button" variant="ghost" aria-expanded={advancedOpen} aria-controls="chat-advanced-filters" onClick={() => setAdvancedOpen((value) => !value)} disabled={pending}>
          {advancedOpen ? "Ocultar filtros avanzados" : "Filtros avanzados"}
        </Button>
        {advancedOpen ? (
          <fieldset id="chat-advanced-filters" className={styles.filterFieldset} disabled={pending}>
            <legend>Delimitar corpus</legend>
            <Stack gap="md">
              <CorpusSelector documents={documents} documentId={documentId} documentType={documentType} knowledgeLayer={knowledgeLayer} onDocumentIdChange={setDocumentId} onDocumentTypeChange={setDocumentType} onKnowledgeLayerChange={setKnowledgeLayer} />
              <FormField label="Modo de coincidencia">
                {(props) => <Select {...props} value={textMatchMode} onChange={(event) => setTextMatchMode(event.target.value as RagChatInput["textMatchMode"])}><option value="all_terms">Todos los términos</option><option value="any_term">Cualquier término</option><option value="phrase">Frase exacta</option></Select>}
              </FormField>
              <FormField label="Cantidad de evidencia a recuperar">
                {(props) => <Select {...props} value={topK} onChange={(event) => setTopK(Number(event.target.value))}>{TOP_K_VALUES.map((value) => <option key={value} value={value}>{value}</option>)}</Select>}
              </FormField>
              <div className={styles.pageFilters}>
                <FormField label="Página mínima" error={minPage && parsedMinPage === undefined ? "Ingresa un número entero desde 1." : undefined}>{(props) => <TextInput {...props} type="number" min="1" inputMode="numeric" value={minPage} onChange={(event) => setMinPage(event.target.value)} />}</FormField>
                <FormField label="Página máxima" error={maxPage && parsedMaxPage === undefined ? "Ingresa un número entero desde 1." : pageRangeInvalid ? "La página máxima no puede ser menor que la mínima." : undefined}>{(props) => <TextInput {...props} type="number" min="1" inputMode="numeric" value={maxPage} onChange={(event) => setMaxPage(event.target.value)} />}</FormField>
              </div>
            </Stack>
          </fieldset>
        ) : null}
        <Inline gap="sm" wrap>
          <Button type="submit" loading={pending} disabled={disabled}>{pending ? "Consultando evidencia y preparando la respuesta local…" : "Consultar"}</Button>
          {canCancel ? <Button type="button" variant="secondary" onClick={onCancel}>Cancelar</Button> : null}
        </Inline>
      </Stack>
    </form>
  );
}
