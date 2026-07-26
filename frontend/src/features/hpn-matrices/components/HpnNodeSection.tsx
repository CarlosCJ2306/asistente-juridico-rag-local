import { useState, type FormEvent } from "react";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import {
  Badge,
  Button,
  Card,
  EmptyState,
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
import { useCreateHpnNode, useDeleteHpnNode, useDeleteHpnSource, useUpdateHpnNode } from "../hooks";
import { isHpnNodeType, isHpnReviewStatus, type HpnId, type HpnNode, type HpnNodeCreateInput, type HpnNodeType, type HpnNodeUpdateInput, type HpnReviewStatus, type HpnSource } from "../types";
import {
  DOCUMENT_TYPE_LABELS,
  hasUnsafeControlCharacters,
  HPN_LIMITS,
  NODE_TYPE_LABELS,
  modalDismissProps,
  pageRange,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_VARIANTS,
  SOURCE_STATUS_LABELS,
  SOURCE_STATUS_VARIANTS,
} from "../utils";
import styles from "../hpnMatrices.module.css";

interface NodeFields {
  readonly nodeType: HpnNodeType;
  readonly title: string;
  readonly statement: string;
  readonly reviewStatus: HpnReviewStatus;
  readonly displayOrder: string;
}

interface NodeErrors { readonly title?: string; readonly statement?: string; readonly displayOrder?: string }

function validateNode(fields: NodeFields): NodeErrors {
  const title = !fields.title.trim() ? "El título es obligatorio." : hasUnsafeControlCharacters(fields.title) ? "El título incluye caracteres de control no permitidos." : undefined;
  const statement = !fields.statement.trim() ? "El contenido es obligatorio." : hasUnsafeControlCharacters(fields.statement) ? "El contenido incluye caracteres de control no permitidos." : undefined;
  const order = Number(fields.displayOrder);
  const displayOrder = !Number.isInteger(order) || order < 1 ? "El orden debe ser un entero mayor o igual que uno." : undefined;
  return { title, statement, displayOrder };
}

interface NodeFormProps {
  readonly initial?: HpnNode;
  readonly defaultOrder: number;
  readonly pending: boolean;
  readonly error: unknown;
  readonly onCancel: () => void;
  readonly onSubmit: (payload: HpnNodeCreateInput | HpnNodeUpdateInput) => Promise<void>;
}

function NodeForm({ initial, defaultOrder, pending, error, onCancel, onSubmit }: NodeFormProps) {
  const [fields, setFields] = useState<NodeFields>({
    nodeType: initial?.nodeType ?? "fact",
    title: initial?.title ?? "",
    statement: initial?.statement ?? "",
    reviewStatus: initial?.reviewStatus ?? "draft",
    displayOrder: String(initial?.displayOrder ?? defaultOrder),
  });
  const [validationErrors, setValidationErrors] = useState<NodeErrors>({});
  const normalizedTitle = fields.title.trim();
  const normalizedStatement = fields.statement.trim();
  const numericOrder = Number(fields.displayOrder);
  const dirty = !initial
    || normalizedTitle !== initial.title
    || normalizedStatement !== initial.statement
    || fields.reviewStatus !== initial.reviewStatus
    || numericOrder !== initial.displayOrder;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issues = validateNode(fields);
    setValidationErrors(issues);
    if (issues.title || issues.statement || issues.displayOrder) return;
    try {
      if (!initial) {
        await onSubmit({ nodeType: fields.nodeType, title: normalizedTitle, statement: normalizedStatement, reviewStatus: fields.reviewStatus, displayOrder: numericOrder });
        return;
      }
      if (!dirty) return;
      const update: HpnNodeUpdateInput = {};
      if (normalizedTitle !== initial.title) Object.assign(update, { title: normalizedTitle });
      if (normalizedStatement !== initial.statement) Object.assign(update, { statement: normalizedStatement });
      if (fields.reviewStatus !== initial.reviewStatus) Object.assign(update, { reviewStatus: fields.reviewStatus });
      if (numericOrder !== initial.displayOrder) Object.assign(update, { displayOrder: numericOrder });
      await onSubmit(update);
    } catch {
      // La mutation conserva el error seguro y los valores del formulario.
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} noValidate autoComplete="off">
      <Stack gap="md">
        <ProfessionalReviewNotice variant="compact" />
        {!initial ? (
          <FormField label="Tipo" required>
            {(props) => <Select {...props} value={fields.nodeType} disabled={pending} onChange={(event) => { if (isHpnNodeType(event.target.value)) setFields({ ...fields, nodeType: event.target.value }); }}>{Object.entries(NODE_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>}
          </FormField>
        ) : <Text variant="secondary">Tipo: {NODE_TYPE_LABELS[initial.nodeType]}. El tipo no se modifica después de crear el elemento.</Text>}
        <FormField label="Título" required error={validationErrors.title} counter={`${fields.title.length}/${HPN_LIMITS.nodeTitle}`}>
          {(props) => <TextInput {...props} value={fields.title} maxLength={HPN_LIMITS.nodeTitle} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, title: undefined }); setFields({ ...fields, title: event.target.value }); }} />}
        </FormField>
        <FormField label="Enunciado" required description="Registro manual sujeto a revisión profesional." error={validationErrors.statement} counter={`${fields.statement.length}/${HPN_LIMITS.nodeStatement}`}>
          {(props) => <Textarea {...props} value={fields.statement} maxLength={HPN_LIMITS.nodeStatement} rows={7} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, statement: undefined }); setFields({ ...fields, statement: event.target.value }); }} />}
        </FormField>
        <FormField label="Estado de revisión" required description="Una evidencia o norma revisada debe conservar una fuente disponible.">
          {(props) => <Select {...props} value={fields.reviewStatus} disabled={pending} onChange={(event) => { if (isHpnReviewStatus(event.target.value)) setFields({ ...fields, reviewStatus: event.target.value }); }}>{Object.entries(REVIEW_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>}
        </FormField>
        <FormField label="Orden" required error={validationErrors.displayOrder}>
          {(props) => <TextInput {...props} type="number" min={1} step={1} value={fields.displayOrder} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, displayOrder: undefined }); setFields({ ...fields, displayOrder: event.target.value }); }} />}
        </FormField>
        {error ? <p role="alert" className={styles.formError}>{toAppError(error).userMessage}</p> : null}
        <Inline gap="sm" justify="end"><Button variant="ghost" onClick={onCancel} disabled={pending}>Cancelar</Button><Button type="submit" loading={pending} disabled={pending || !dirty}>{initial ? "Guardar elemento" : "Crear elemento"}</Button></Inline>
      </Stack>
    </form>
  );
}

interface ConfirmDialogProps {
  readonly open: boolean;
  readonly title: string;
  readonly description: string;
  readonly actionLabel: string;
  readonly pending: boolean;
  readonly error: unknown;
  readonly onClose: () => void;
  readonly onConfirm: () => Promise<void>;
}

function ConfirmDialog({ open, title, description, actionLabel, pending, error, onClose, onConfirm }: ConfirmDialogProps) {
  return <Modal open={open} onOpenChange={(next) => { if (!next) onClose(); }} title={title} description={description} {...modalDismissProps(pending)}><Stack gap="md">{error ? <p role="alert" className={styles.formError}>{toAppError(error).userMessage}</p> : null}<Inline gap="sm" justify="end"><Button variant="ghost" disabled={pending} onClick={onClose}>Cancelar</Button><Button variant="danger" loading={pending} onClick={() => { void onConfirm().catch(() => undefined); }}>{actionLabel}</Button></Inline></Stack></Modal>;
}

function SourceItem({ matrixId, nodeId, source, readOnly }: { readonly matrixId: HpnId; readonly nodeId: HpnId; readonly source: HpnSource; readonly readOnly: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const deletion = useDeleteHpnSource();
  async function remove() { await deletion.mutateAsync({ matrixId, nodeId, sourceId: source.sourceId }); setConfirming(false); }
  return (
    <li className={styles.sourceItem}>
      <Stack gap="sm">
        <Inline gap="sm" justify="between" align="start"><Text className={styles.sourceName} variant="label">{source.documentName}</Text><Badge variant={SOURCE_STATUS_VARIANTS[source.sourceStatus]}>{SOURCE_STATUS_LABELS[source.sourceStatus]}</Badge></Inline>
        <Text variant="secondary">{DOCUMENT_TYPE_LABELS[source.documentType]} · {pageRange(source.startPage, source.endPage)} · chunk {source.chunkIndex}</Text>
        {!readOnly ? <div><Button size="sm" variant="ghost" onClick={() => { deletion.reset(); setConfirming(true); }}>Desvincular fuente</Button></div> : null}
      </Stack>
      <ConfirmDialog open={confirming} title="Desvincular fuente" description="La fuente dejará de respaldar este elemento; el documento original no se modifica." actionLabel="Desvincular" pending={deletion.isPending} error={deletion.error} onClose={() => setConfirming(false)} onConfirm={remove} />
    </li>
  );
}

function NodeItem({ matrixId, node, readOnly, defaultOrder }: { readonly matrixId: HpnId; readonly node: HpnNode; readonly readOnly: boolean; readonly defaultOrder: number }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const update = useUpdateHpnNode();
  const deletion = useDeleteHpnNode();
  async function save(payload: HpnNodeCreateInput | HpnNodeUpdateInput) { await update.mutateAsync({ matrixId, nodeId: node.id, payload }); setEditing(false); }
  async function remove() { await deletion.mutateAsync({ matrixId, nodeId: node.id }); setDeleting(false); }
  return (
    <li><Card className={styles.itemCard}>
      <Stack gap="md">
        <div className={styles.itemHeader}><div><Inline gap="sm"><Badge variant="info">{NODE_TYPE_LABELS[node.nodeType]}</Badge><Badge variant={REVIEW_STATUS_VARIANTS[node.reviewStatus]}>{REVIEW_STATUS_LABELS[node.reviewStatus]}</Badge></Inline><Heading as="h3" size="sm">{node.title}</Heading></div>{!readOnly ? <div className={styles.actions}><Button size="sm" variant="secondary" onClick={() => { update.reset(); setEditing(true); }}>Editar</Button><Button size="sm" variant="danger" onClick={() => { deletion.reset(); setDeleting(true); }}>Eliminar</Button></div> : null}</div>
        <Text className={styles.statement}>{node.statement}</Text>
        <Text variant="caption">Orden de presentación: {node.displayOrder}</Text>
        <div><Heading as="h4" size="sm">Fuentes vinculadas</Heading>{node.sources.length ? <ul className={styles.sourceList}>{node.sources.map((source) => <SourceItem key={source.sourceId} matrixId={matrixId} nodeId={node.id} source={source} readOnly={readOnly} />)}</ul> : <Text variant="secondary">Este elemento no tiene fuentes vinculadas.</Text>}</div>
      </Stack>
    </Card>
    {editing ? <Modal open title="Editar elemento" description="Los cambios estructurales en una matriz revisada pueden devolverla a revisión." onOpenChange={(open) => { if (!open) setEditing(false); }} size="lg" {...modalDismissProps(update.isPending)}><NodeForm initial={node} defaultOrder={defaultOrder} pending={update.isPending} error={update.error} onCancel={() => setEditing(false)} onSubmit={save} /></Modal> : null}
    <ConfirmDialog open={deleting} title="Eliminar elemento" description="También dejarán de estar disponibles sus relaciones y vínculos dentro de la matriz." actionLabel="Eliminar elemento" pending={deletion.isPending} error={deletion.error} onClose={() => setDeleting(false)} onConfirm={remove} />
    </li>
  );
}

export function HpnNodeSection({ matrixId, nodes, readOnly }: { readonly matrixId: HpnId; readonly nodes: readonly HpnNode[]; readonly readOnly: boolean }) {
  const [creating, setCreating] = useState(false);
  const creation = useCreateHpnNode();
  const defaultOrder = Math.max(0, ...nodes.map((node) => node.displayOrder)) + 1;
  function openCreation() { creation.reset(); setCreating(true); }
  async function create(payload: HpnNodeCreateInput | HpnNodeUpdateInput) {
    if (!("nodeType" in payload)) return;
    await creation.mutateAsync({ matrixId, payload });
    setCreating(false);
  }
  return (
    <Card as="section" className={styles.sectionCard} padding="lg">
      <Stack gap="md">
        <div className={styles.sectionHeader}><div><Heading as="h2">Elementos HPN</Heading><Text variant="secondary">Hechos, evidencias y normas registrados manualmente. Sus estados son de revisión, no conclusiones jurídicas.</Text></div>{!readOnly ? <Button onClick={openCreation}>Agregar elemento</Button> : null}</div>
        {nodes.length ? <ul className={styles.nodeList}>{nodes.map((node) => <NodeItem key={node.id} matrixId={matrixId} node={node} readOnly={readOnly} defaultOrder={defaultOrder} />)}</ul> : <EmptyState title="Matriz sin elementos" description="Agrega el primer hecho, evidencia o norma para estructurar el análisis manual." action={!readOnly ? <Button onClick={openCreation}>Agregar elemento</Button> : undefined} />}
      </Stack>
      {creating ? <Modal open title="Agregar elemento" description="Registra contenido manual para revisión profesional." onOpenChange={(open) => { if (!open) setCreating(false); }} size="lg" {...modalDismissProps(creation.isPending)}><NodeForm defaultOrder={defaultOrder} pending={creation.isPending} error={creation.error} onCancel={() => setCreating(false)} onSubmit={create} /></Modal> : null}
    </Card>
  );
}
