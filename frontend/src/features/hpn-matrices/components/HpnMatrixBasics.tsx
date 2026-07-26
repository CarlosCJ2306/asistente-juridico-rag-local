import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import {
  Badge,
  Button,
  Card,
  FormField,
  Heading,
  Inline,
  Modal,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "../../../design-system";
import { isHpnMatrixStatus, type HpnMatrix, type HpnMatrixCreateInput, type HpnMatrixUpdateInput } from "../types";
import {
  formatHpnDate,
  hasUnsafeControlCharacters,
  HPN_LIMITS,
  MATRIX_STATUS_LABELS,
  MATRIX_STATUS_VARIANTS,
  matrixStatusOptions,
  modalDismissProps,
} from "../utils";
import styles from "../hpnMatrices.module.css";

interface MatrixFields {
  readonly title: string;
  readonly description: string;
  readonly status: HpnMatrix["status"];
}

interface MatrixErrors { readonly title?: string; readonly description?: string }

function validateMatrix(fields: MatrixFields): MatrixErrors {
  const title = !fields.title.trim()
    ? "El título es obligatorio."
    : hasUnsafeControlCharacters(fields.title) ? "El título incluye caracteres de control no permitidos." : undefined;
  const description = hasUnsafeControlCharacters(fields.description)
    ? "La descripción incluye caracteres de control no permitidos."
    : undefined;
  return { title, description };
}

export function HpnMatrixStatus({ matrix }: { readonly matrix: HpnMatrix }) {
  return <Badge variant={MATRIX_STATUS_VARIANTS[matrix.status]}>{MATRIX_STATUS_LABELS[matrix.status]}</Badge>;
}

export function HpnMatrixCard({ matrix }: { readonly matrix: HpnMatrix }) {
  return (
    <Card className={styles.matrixCard}>
      <Stack gap="sm">
        <Inline gap="sm" justify="between" align="start">
          <Heading as="h2" size="sm"><Link className={styles.titleLink} to={`/matrices-hpn/${matrix.id}`}>{matrix.title}</Link></Heading>
          <HpnMatrixStatus matrix={matrix} />
        </Inline>
        {matrix.description ? <Text variant="secondary" className={styles.clampedText}>{matrix.description}</Text> : <Text variant="secondary">Sin descripción.</Text>}
        <Text variant="caption">Actualizada: {formatHpnDate(matrix.updatedAt)}</Text>
        <div><Link className={styles.secondaryLink} to={`/matrices-hpn/${matrix.id}`}>Abrir matriz</Link></div>
      </Stack>
    </Card>
  );
}

interface MatrixFormProps {
  readonly initial?: HpnMatrix;
  readonly pending: boolean;
  readonly error: unknown;
  readonly onCancel: () => void;
  readonly onSubmit: (payload: HpnMatrixCreateInput | HpnMatrixUpdateInput) => Promise<void>;
}

export function HpnMatrixForm({ initial, pending, error, onCancel, onSubmit }: MatrixFormProps) {
  const [fields, setFields] = useState<MatrixFields>({
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    status: initial?.status ?? "draft",
  });
  const [validationErrors, setValidationErrors] = useState<MatrixErrors>({});
  const normalizedTitle = fields.title.trim();
  const normalizedDescription = fields.description.trim() || null;
  const dirty = !initial
    || normalizedTitle !== initial.title
    || normalizedDescription !== initial.description
    || fields.status !== initial.status;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issues = validateMatrix(fields);
    setValidationErrors(issues);
    if (issues.title || issues.description) return;
    try {
      if (!initial) {
        await onSubmit({ title: normalizedTitle, description: normalizedDescription });
        return;
      }
      if (!dirty) return;
      const patch: HpnMatrixUpdateInput = {};
      if (normalizedTitle !== initial.title) Object.assign(patch, { title: normalizedTitle });
      if (normalizedDescription !== initial.description) Object.assign(patch, { description: normalizedDescription });
      if (fields.status !== initial.status) Object.assign(patch, { status: fields.status });
      await onSubmit(patch);
    } catch {
      // La mutation conserva el error seguro y los valores del formulario.
    }
  }

  const serverError = error ? toAppError(error).userMessage : null;
  return (
    <form onSubmit={(event) => void submit(event)} noValidate autoComplete="off">
      <Stack gap="md">
        <ProfessionalReviewNotice variant="compact" />
        <FormField label="Título" required error={validationErrors.title} counter={`${fields.title.length}/${HPN_LIMITS.matrixTitle}`}>
          {(props) => <TextInput {...props} value={fields.title} maxLength={HPN_LIMITS.matrixTitle} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, title: undefined }); setFields({ ...fields, title: event.target.value }); }} />}
        </FormField>
        <FormField label="Descripción" error={validationErrors.description} counter={`${fields.description.length}/${HPN_LIMITS.matrixDescription}`}>
          {(props) => <Textarea {...props} value={fields.description} maxLength={HPN_LIMITS.matrixDescription} rows={5} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, description: undefined }); setFields({ ...fields, description: event.target.value }); }} />}
        </FormField>
        {initial ? (
          <FormField label="Estado" description="Las transiciones se validan también en el servicio local.">
            {(props) => (
              <Select {...props} value={fields.status} disabled={pending || initial.status === "archived"} onChange={(event) => { if (isHpnMatrixStatus(event.target.value)) setFields({ ...fields, status: event.target.value }); }}>
                {matrixStatusOptions(initial.status).map((status) => <option key={status} value={status}>{MATRIX_STATUS_LABELS[status]}</option>)}
              </Select>
            )}
          </FormField>
        ) : null}
        {serverError ? <p role="alert" className={styles.formError}>{serverError}</p> : null}
        <Inline gap="sm" justify="end">
          <Button variant="ghost" onClick={onCancel} disabled={pending}>Cancelar</Button>
          <Button type="submit" loading={pending} disabled={pending || !dirty}>{initial ? "Guardar cambios" : "Crear matriz"}</Button>
        </Inline>
      </Stack>
    </form>
  );
}

interface DeleteMatrixDialogProps {
  readonly publicLabel: string;
  readonly open: boolean;
  readonly pending: boolean;
  readonly error: unknown;
  readonly onClose: () => void;
  readonly onConfirm: () => Promise<void>;
}

export function DeleteMatrixDialog({ publicLabel, open, pending, error, onClose, onConfirm }: DeleteMatrixDialogProps) {
  return (
    <Modal open={open} onOpenChange={(next) => { if (!next) onClose(); }} title="Eliminar matriz" description="La matriz dejará de estar disponible. Esta acción no constituye una valoración jurídica." {...modalDismissProps(pending)}>
      <Stack gap="md">
        <Text>Confirma la eliminación de la matriz “{publicLabel}” y sus elementos asociados.</Text>
        {error ? <p role="alert" className={styles.formError}>{toAppError(error).userMessage}</p> : null}
        <Inline gap="sm" justify="end">
          <Button variant="ghost" onClick={onClose} disabled={pending}>Cancelar</Button>
          <Button variant="danger" loading={pending} onClick={() => { void onConfirm().catch(() => undefined); }}>Eliminar matriz</Button>
        </Inline>
      </Stack>
    </Modal>
  );
}
