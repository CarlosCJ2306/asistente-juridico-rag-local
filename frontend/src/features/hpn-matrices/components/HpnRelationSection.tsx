import { useState, type FormEvent } from "react";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { Badge, Button, Card, EmptyState, FormField, Heading, Inline, Modal, Select, Stack, Text, Textarea } from "../../../design-system";
import { useCreateHpnRelation, useDeleteHpnRelation, useUpdateHpnRelation } from "../hooks";
import { isHpnId, isHpnRelationType, isHpnReviewStatus, type HpnId, type HpnNode, type HpnRelation, type HpnRelationCreateInput, type HpnRelationType, type HpnRelationUpdateInput, type HpnReviewStatus } from "../types";
import { hasUnsafeControlCharacters, HPN_LIMITS, modalDismissProps, NODE_TYPE_LABELS, RELATION_TYPE_LABELS, relationSourceType, REVIEW_STATUS_LABELS, REVIEW_STATUS_VARIANTS } from "../utils";
import styles from "../hpnMatrices.module.css";

const RELATION_TYPES = [
  "evidence_supports_fact",
  "evidence_contradicts_fact",
  "norm_applies_to_fact",
  "norm_limits_fact",
] satisfies readonly HpnRelationType[];

interface RelationFields {
  readonly relationType: HpnRelationType;
  readonly sourceNodeId: string;
  readonly targetNodeId: string;
  readonly rationale: string;
  readonly reviewStatus: HpnReviewStatus;
}

interface RelationErrors { readonly sourceNodeId?: string; readonly targetNodeId?: string; readonly rationale?: string }

function validateRelation(fields: RelationFields, editing: boolean): RelationErrors {
  return {
    sourceNodeId: !editing && !fields.sourceNodeId ? "Selecciona el elemento de origen." : undefined,
    targetNodeId: !editing && !fields.targetNodeId ? "Selecciona el hecho de destino." : undefined,
    rationale: hasUnsafeControlCharacters(fields.rationale) ? "La justificación incluye caracteres de control no permitidos." : undefined,
  };
}

function nodeOptionLabel(node: HpnNode): string {
  return `${NODE_TYPE_LABELS[node.nodeType]} ${node.displayOrder}: ${node.title}`;
}

interface RelationFormProps {
  readonly nodes: readonly HpnNode[];
  readonly initial?: HpnRelation;
  readonly pending: boolean;
  readonly error: unknown;
  readonly onCancel: () => void;
  readonly onSubmit: (payload: HpnRelationCreateInput | HpnRelationUpdateInput) => Promise<void>;
}

function RelationForm({ nodes, initial, pending, error, onCancel, onSubmit }: RelationFormProps) {
  const initialType = initial?.relationType ?? "evidence_supports_fact";
  const [fields, setFields] = useState<RelationFields>({ relationType: initialType, sourceNodeId: initial?.sourceNodeId ?? "", targetNodeId: initial?.targetNodeId ?? "", rationale: initial?.rationale ?? "", reviewStatus: initial?.reviewStatus ?? "draft" });
  const [validationErrors, setValidationErrors] = useState<RelationErrors>({});
  const sourceType = relationSourceType(fields.relationType);
  const sourceNodes = nodes.filter((node) => node.nodeType === sourceType);
  const factNodes = nodes.filter((node) => node.nodeType === "fact");
  const normalizedRationale = fields.rationale.trim() || null;
  const dirty = !initial
    || normalizedRationale !== initial.rationale
    || fields.reviewStatus !== initial.reviewStatus;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issues = validateRelation(fields, Boolean(initial));
    setValidationErrors(issues);
    if (issues.sourceNodeId || issues.targetNodeId || issues.rationale) return;
    try {
      if (initial) {
        if (!dirty) return;
        const update: HpnRelationUpdateInput = {};
        if (normalizedRationale !== initial.rationale) Object.assign(update, { rationale: normalizedRationale });
        if (fields.reviewStatus !== initial.reviewStatus) Object.assign(update, { reviewStatus: fields.reviewStatus });
        await onSubmit(update);
        return;
      }
      if (!isHpnId(fields.sourceNodeId) || !isHpnId(fields.targetNodeId)) {
        setValidationErrors({ sourceNodeId: "Selecciona un elemento de origen válido.", targetNodeId: "Selecciona un hecho de destino válido." });
        return;
      }
      await onSubmit({ sourceNodeId: fields.sourceNodeId, targetNodeId: fields.targetNodeId, relationType: fields.relationType, rationale: normalizedRationale, reviewStatus: fields.reviewStatus });
    } catch {
      // La mutation conserva el error seguro y los valores del formulario.
    }
  }

  function changeType(relationType: HpnRelationType) {
    setValidationErrors({ ...validationErrors, sourceNodeId: undefined });
    setFields({ ...fields, relationType, sourceNodeId: "" });
  }

  return (
    <form onSubmit={(event) => void submit(event)} noValidate autoComplete="off">
      <Stack gap="md">
        <ProfessionalReviewNotice variant="compact" />
        {!initial ? <>
          <FormField label="Tipo de relación" required>{(props) => <Select {...props} value={fields.relationType} disabled={pending} onChange={(event) => { if (isHpnRelationType(event.target.value)) changeType(event.target.value); }}>{RELATION_TYPES.map((type) => <option key={type} value={type}>{RELATION_TYPE_LABELS[type]}</option>)}</Select>}</FormField>
          <FormField label={`${NODE_TYPE_LABELS[sourceType]} de origen`} required error={validationErrors.sourceNodeId}>{(props) => <Select {...props} value={fields.sourceNodeId} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, sourceNodeId: undefined }); setFields({ ...fields, sourceNodeId: event.target.value }); }}><option value="">Selecciona un elemento</option>{sourceNodes.map((node) => <option key={node.id} value={node.id}>{nodeOptionLabel(node)}</option>)}</Select>}</FormField>
          <FormField label="Hecho de destino" required error={validationErrors.targetNodeId}>{(props) => <Select {...props} value={fields.targetNodeId} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, targetNodeId: undefined }); setFields({ ...fields, targetNodeId: event.target.value }); }}><option value="">Selecciona un hecho</option>{factNodes.map((node) => <option key={node.id} value={node.id}>{nodeOptionLabel(node)}</option>)}</Select>}</FormField>
        </> : <Text variant="secondary">Los extremos y el tipo de una relación existente no pueden modificarse.</Text>}
        <FormField label="Justificación" error={validationErrors.rationale} counter={`${fields.rationale.length}/${HPN_LIMITS.relationRationale}`}>{(props) => <Textarea {...props} value={fields.rationale} maxLength={HPN_LIMITS.relationRationale} rows={5} disabled={pending} onChange={(event) => { setValidationErrors({ ...validationErrors, rationale: undefined }); setFields({ ...fields, rationale: event.target.value }); }} />}</FormField>
        <FormField label="Estado de revisión" required>{(props) => <Select {...props} value={fields.reviewStatus} disabled={pending} onChange={(event) => { if (isHpnReviewStatus(event.target.value)) setFields({ ...fields, reviewStatus: event.target.value }); }}>{Object.entries(REVIEW_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>}</FormField>
        {error ? <p role="alert" className={styles.formError}>{toAppError(error).userMessage}</p> : null}
        <Inline gap="sm" justify="end"><Button variant="ghost" disabled={pending} onClick={onCancel}>Cancelar</Button><Button type="submit" loading={pending} disabled={pending || !dirty}>{initial ? "Guardar relación" : "Crear relación"}</Button></Inline>
      </Stack>
    </form>
  );
}

function RelationItem({ matrixId, relation, nodes, readOnly }: { readonly matrixId: HpnId; readonly relation: HpnRelation; readonly nodes: readonly HpnNode[]; readonly readOnly: boolean }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const update = useUpdateHpnRelation();
  const deletion = useDeleteHpnRelation();
  const byId = new Map(nodes.map((node) => [node.id, nodeOptionLabel(node)]));
  const sourceTitle = byId.get(relation.sourceNodeId) ?? "Elemento de origen no disponible";
  const targetTitle = byId.get(relation.targetNodeId) ?? "Elemento de destino no disponible";
  async function save(payload: HpnRelationCreateInput | HpnRelationUpdateInput) { if ("sourceNodeId" in payload) return; await update.mutateAsync({ matrixId, relationId: relation.id, payload }); setEditing(false); }
  async function remove() { await deletion.mutateAsync({ matrixId, relationId: relation.id }); setDeleting(false); }
  return (
    <li><Card className={styles.itemCard}>
      <Stack gap="sm">
        <div className={styles.itemHeader}><div><Badge variant={REVIEW_STATUS_VARIANTS[relation.reviewStatus]}>{REVIEW_STATUS_LABELS[relation.reviewStatus]}</Badge><Heading as="h3" size="sm">{RELATION_TYPE_LABELS[relation.relationType]}</Heading></div>{!readOnly ? <div className={styles.actions}><Button size="sm" variant="secondary" onClick={() => { update.reset(); setEditing(true); }}>Editar</Button><Button size="sm" variant="danger" onClick={() => { deletion.reset(); setDeleting(true); }}>Eliminar</Button></div> : null}</div>
        <Text><strong>Origen:</strong> {sourceTitle}</Text><Text><strong>Destino:</strong> {targetTitle}</Text>
        {relation.rationale ? <Text className={styles.rationale} variant="secondary">{relation.rationale}</Text> : <Text variant="secondary">Sin justificación registrada.</Text>}
      </Stack>
    </Card>
    {editing ? <Modal open title="Editar relación" description="La interpretación de la relación corresponde a una revisión profesional." onOpenChange={(open) => { if (!open) setEditing(false); }} size="lg" {...modalDismissProps(update.isPending)}><RelationForm nodes={nodes} initial={relation} pending={update.isPending} error={update.error} onCancel={() => setEditing(false)} onSubmit={save} /></Modal> : null}
    <Modal open={deleting} title="Eliminar relación" description="Los elementos relacionados se conservarán." onOpenChange={(open) => { if (!open) setDeleting(false); }} {...modalDismissProps(deletion.isPending)}><Stack gap="md">{deletion.error ? <p role="alert" className={styles.formError}>{toAppError(deletion.error).userMessage}</p> : null}<Inline gap="sm" justify="end"><Button variant="ghost" disabled={deletion.isPending} onClick={() => setDeleting(false)}>Cancelar</Button><Button variant="danger" loading={deletion.isPending} onClick={() => { void remove().catch(() => undefined); }}>Eliminar relación</Button></Inline></Stack></Modal>
    </li>
  );
}

export function HpnRelationSection({ matrixId, nodes, relations, readOnly }: { readonly matrixId: HpnId; readonly nodes: readonly HpnNode[]; readonly relations: readonly HpnRelation[]; readonly readOnly: boolean }) {
  const [creating, setCreating] = useState(false);
  const creation = useCreateHpnRelation();
  const canCreate = nodes.some((node) => node.nodeType === "fact") && nodes.some((node) => node.nodeType === "evidence" || node.nodeType === "norm");
  function openCreation() { creation.reset(); setCreating(true); }
  async function create(payload: HpnRelationCreateInput | HpnRelationUpdateInput) { if (!("sourceNodeId" in payload)) return; await creation.mutateAsync({ matrixId, payload }); setCreating(false); }
  return (
    <Card as="section" className={styles.sectionCard} padding="lg"><Stack gap="md"><div className={styles.sectionHeader}><div><Heading as="h2">Relaciones dirigidas</Heading><Text variant="secondary">Vínculos estructurales permitidos entre evidencias o normas y hechos. No demuestran causalidad ni aplicabilidad jurídica.</Text></div>{!readOnly && canCreate ? <Button onClick={openCreation}>Agregar relación</Button> : null}</div>{relations.length ? <ul className={styles.relationList}>{relations.map((relation) => <RelationItem key={relation.id} matrixId={matrixId} relation={relation} nodes={nodes} readOnly={readOnly} />)}</ul> : <EmptyState title="Sin relaciones" description={canCreate ? "Crea una relación dirigida entre los elementos compatibles de la matriz." : "Se necesita al menos un hecho y una evidencia o norma para crear relaciones."} action={!readOnly && canCreate ? <Button onClick={openCreation}>Agregar relación</Button> : undefined} />}</Stack>{creating ? <Modal open title="Agregar relación" description="Solo se admiten las combinaciones definidas por el contrato HPN." onOpenChange={(open) => { if (!open) setCreating(false); }} size="lg" {...modalDismissProps(creation.isPending)}><RelationForm nodes={nodes} pending={creation.isPending} error={creation.error} onCancel={() => setCreating(false)} onSubmit={create} /></Modal> : null}</Card>
  );
}
