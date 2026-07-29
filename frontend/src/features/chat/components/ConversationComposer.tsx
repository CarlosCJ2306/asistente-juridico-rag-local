import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import { Button, Inline, Textarea } from "../../../design-system";
import type { ConversationInput } from "../types";
import styles from "../chat.module.css";

const MAX_LENGTH = 500;

interface ConversationComposerProps {
  readonly value: string;
  readonly pending: boolean;
  readonly onChange: (value: string) => void;
  readonly onSubmit: (input: ConversationInput) => void;
  readonly onCancel: () => void;
}

export function ConversationComposer({ value, pending, onChange, onSubmit, onCancel }: ConversationComposerProps) {
  const composing = useRef(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const normalized = value.trim();
  const invalid = value.length > MAX_LENGTH;
  const disabled = !normalized || invalid || pending;

  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }, [value]);

  function submit() {
    if (disabled || composing.current) return;
    onSubmit({ question: normalized, textMatchMode: "all_terms", topK: 8 });
  }
  function handleSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); submit(); }
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !composing.current) { event.preventDefault(); submit(); }
  }

  return <form className={styles.composerForm} onSubmit={handleSubmit}><div className={styles.composerSurface}><Textarea ref={textarea} className={styles.composerTextarea} aria-label="Pregunta jurídica" aria-describedby={invalid ? "conversation-composer-error" : "conversation-composer-hint"} value={value} maxLength={MAX_LENGTH + 1} placeholder="Escribe una pregunta o repregunta…" onChange={(event) => onChange(event.target.value)} onKeyDown={handleKeyDown} onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }} disabled={pending} /><div className={styles.composerToolbar}><span id="conversation-composer-hint" className={styles.composerCounter}>{value.length}/{MAX_LENGTH}</span><Inline gap="sm" wrap>{pending ? <Button type="button" variant="secondary" onClick={onCancel}>Cancelar</Button> : null}<Button type="submit" loading={pending} disabled={disabled}>{pending ? "Procesando…" : "Enviar"}</Button></Inline></div></div>{invalid ? <p id="conversation-composer-error" className={styles.composerError}>La pregunta no puede superar {MAX_LENGTH} caracteres.</p> : null}</form>;
}
