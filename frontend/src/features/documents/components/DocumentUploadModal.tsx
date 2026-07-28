import { useRef, useState, type ChangeEvent, type FormEvent } from "react";

import { isRequestCancelledError, toAppError } from "../../../api";
import { Button, FormField, Inline, Modal, Radio, Select, Stack, Text, TextInput } from "../../../design-system";
import { modalDismissProps } from "../../hpn-matrices/utils";
import { useDocumentUpload } from "../hooks";
import type { DocumentType, PublicDocument, PublicUploadKnowledgeLayer } from "../types";
import { DOCUMENT_TYPE_LABELS, formatDocumentSize } from "../utils";
import styles from "../documents.module.css";

interface UploadErrors {
  file?: string;
  displayName?: string;
  expiresAt?: string;
}

const DOCUMENT_TYPES: readonly DocumentType[] = ["expediente", "normativa", "jurisprudencia", "otro"];

function hasUnsafeControlCharacters(value: string): boolean {
  return /\p{C}/u.test(value);
}

function toIsoExpiration(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function validationErrors(file: File | null, displayName: string, layer: PublicUploadKnowledgeLayer, expiresAt: string): UploadErrors {
  const errors: UploadErrors = {};
  if (file === null) errors.file = "Selecciona un archivo PDF.";
  else if (!file.name.toLocaleLowerCase("es-CO").endsWith(".pdf")) errors.file = "Selecciona un archivo con extensión .pdf.";
  if (displayName && (displayName.trim().length === 0 || displayName.length > 255 || hasUnsafeControlCharacters(displayName))) {
    errors.displayName = "El nombre visible debe tener hasta 255 caracteres y no incluir caracteres de control.";
  }
  if (layer === "temporary") {
    const isoExpiration = toIsoExpiration(expiresAt);
    if (isoExpiration === null) errors.expiresAt = "Indica una fecha y hora de expiración.";
    else if (Date.parse(isoExpiration) <= Date.now()) errors.expiresAt = "La expiración debe ser una fecha futura.";
  }
  return errors;
}

function uploadErrorMessage(error: unknown): string | null {
  if (isRequestCancelledError(error)) return null;
  const appError = toAppError(error);
  if (appError.category === "conflict") return "El documento ya está registrado en la biblioteca local.";
  if (appError.category === "too_large") return "El archivo supera el tamaño máximo permitido por el backend local.";
  if (appError.code === "DOCUMENT_GOVERNANCE_INVALID") return "La capa o la expiración no cumplen las reglas de carga pública.";
  if (appError.category === "validation") return "Revisa el archivo y los datos de carga antes de volver a intentarlo.";
  if (appError.category === "offline" || appError.category === "network" || appError.category === "unavailable") return "El backend local no está disponible. Comprueba la conexión e inténtalo de nuevo.";
  return "No fue posible registrar el documento. Revisa los datos e inténtalo de nuevo.";
}

interface DocumentUploadModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onCompleted: (document: PublicDocument) => void;
}

export function DocumentUploadModal({ open, onOpenChange, onCompleted }: DocumentUploadModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useDocumentUpload();
  const [file, setFile] = useState<File | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>("otro");
  const [knowledgeLayer, setKnowledgeLayer] = useState<PublicUploadKnowledgeLayer>("private_library");
  const [expiresAt, setExpiresAt] = useState("");
  const [errors, setErrors] = useState<UploadErrors>({});

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.item(0) ?? null;
    setFile(nextFile);
    setErrors((current) => ({ ...current, file: undefined }));
  }

  function selectLayer(layer: PublicUploadKnowledgeLayer) {
    setKnowledgeLayer(layer);
    if (layer === "private_library") setErrors((current) => ({ ...current, expiresAt: undefined }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validationErrors(file, displayName, knowledgeLayer, expiresAt);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean) || file === null || upload.isPending) return;
    const isoExpiration = knowledgeLayer === "temporary" ? toIsoExpiration(expiresAt) : undefined;
    try {
      const document = await upload.mutateAsync({
        file,
        documentType,
        knowledgeLayer,
        displayName: displayName.trim() || undefined,
        expiresAt: isoExpiration ?? undefined,
      });
      if (inputRef.current) inputRef.current.value = "";
      onCompleted(document);
    } catch {
      // La mutation conserva el error seguro y permite corregir el formulario.
    }
  }

  const serverError = upload.error ? uploadErrorMessage(upload.error) : null;
  const temporary = knowledgeLayer === "temporary";
  return (
    <Modal open={open} onOpenChange={onOpenChange} title="Subir PDF" description="El archivo se procesa únicamente en esta instalación local. La carga no aprueba, extrae ni indexa el documento automáticamente." size="lg" {...modalDismissProps(upload.isPending)}>
      <form onSubmit={(event) => void submit(event)} noValidate>
        <Stack gap="md">
          <FormField label="Archivo PDF" required error={errors.file} description="Selecciona un único archivo PDF. El backend valida extensión, MIME, firma y tamaño.">
            {(props) => <input {...props} ref={inputRef} className={styles.fileInput} type="file" accept=".pdf,application/pdf" onChange={selectFile} disabled={upload.isPending} autoFocus />}
          </FormField>
          {file ? <Text variant="secondary" className={styles.selectedFile}>Archivo seleccionado: {file.name} · {formatDocumentSize(file.size)}</Text> : null}
          <FormField label="Nombre visible" error={errors.displayName} description="Opcional. Si se omite, se usa el nombre público registrado por el backend." counter={`${displayName.length}/255`}>
            {(props) => <TextInput {...props} value={displayName} maxLength={255} disabled={upload.isPending} onChange={(event) => { setDisplayName(event.target.value); setErrors((current) => ({ ...current, displayName: undefined })); }} />}
          </FormField>
          <FormField label="Tipo documental" required>
            {(props) => <Select {...props} value={documentType} disabled={upload.isPending} onChange={(event) => setDocumentType(event.target.value as DocumentType)}>{DOCUMENT_TYPES.map((type) => <option key={type} value={type}>{DOCUMENT_TYPE_LABELS[type]}</option>)}</Select>}
          </FormField>
          <fieldset className={styles.purposeFieldset} aria-describedby="document-purpose-description">
            <legend className={styles.purposeLegend}>Propósito documental</legend>
            <Text id="document-purpose-description" variant="secondary">Selecciona cómo se conservará el documento. Esta decisión no habilita automáticamente su uso en consultas.</Text>
            <Radio name="knowledge-layer" value="private_library" checked={knowledgeLayer === "private_library"} disabled={upload.isPending} onChange={() => selectLayer("private_library")} label="Guardar en biblioteca privada" />
            <Text as="p" variant="caption" className={styles.purposeDescription}>El documento permanecerá en la biblioteca local para futuras consultas.</Text>
            <Radio name="knowledge-layer" value="temporary" checked={temporary} disabled={upload.isPending} onChange={() => selectLayer("temporary")} label="Consultar temporalmente" />
            <Text as="p" variant="caption" className={styles.purposeDescription}>El documento quedará excluido de futuras consultas después de su vencimiento. La expiración no implica borrado físico automático.</Text>
          </fieldset>
          {temporary ? <FormField label="Expiración" required error={errors.expiresAt} description="La fecha se enviará con zona horaria al backend local.">{(props) => <TextInput {...props} type="datetime-local" value={expiresAt} disabled={upload.isPending} invalid={Boolean(errors.expiresAt)} onChange={(event) => { setExpiresAt(event.target.value); setErrors((current) => ({ ...current, expiresAt: undefined })); }} />}</FormField> : null}
          <section className={styles.uploadSummary} aria-label="Resumen de la carga"><Text variant="secondary">Después de registrar el PDF, el documento quedará pendiente de extracción e indexación. Esta pantalla no inicia esos procesos.</Text></section>
          {serverError ? <p className={styles.formError} role="alert">{serverError}</p> : null}
          <Inline gap="sm" justify="end" className={styles.uploadActions}>
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={upload.isPending}>Cancelar</Button>
            <Button type="submit" loading={upload.isPending} disabled={upload.isPending} aria-live="polite">{upload.isPending ? "Subiendo…" : "Subir PDF"}</Button>
          </Inline>
        </Stack>
      </form>
    </Modal>
  );
}
