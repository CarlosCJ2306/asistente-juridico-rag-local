import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, Card, ErrorState, Heading, Inline, Modal, Stack, Text } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { FullWidthLayout } from "../../../layouts";
import { DeleteMatrixDialog, HpnMatrixForm, HpnMatrixStatus, HpnMatrixSummary, HpnNodeSection, HpnRelationSection } from "../components";
import { useDeleteHpnMatrix, useHpnMatrix, useUpdateHpnMatrix } from "../hooks";
import { isHpnId, type HpnId, type HpnMatrixCreateInput, type HpnMatrixUpdateInput } from "../types";
import { formatHpnDate, modalDismissProps } from "../utils";
import styles from "../hpnMatrices.module.css";

function detailStatus(isPending: boolean, error: unknown): AsyncStatus {
  if (isPending) return "loading";
  if (!error) return "success";
  const category = toAppError(error).category;
  if (category === "offline" || category === "network") return "offline";
  if (category === "unauthorized") return "unauthorized";
  if (category === "forbidden") return "forbidden";
  return "error";
}

function HpnMatrixDetailContent({ matrixId }: { readonly matrixId: HpnId }) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const query = useHpnMatrix(matrixId);
  const update = useUpdateHpnMatrix();
  const deletion = useDeleteHpnMatrix();
  const status = detailStatus(query.isPending, query.error);
  const matrix = query.data?.matrix;
  const readOnly = matrix?.status === "archived";

  async function save(payload: HpnMatrixCreateInput | HpnMatrixUpdateInput) {
    if ("title" in payload && payload.title !== undefined && !matrix) return;
    await update.mutateAsync({ matrixId, payload });
    setEditing(false);
  }
  async function remove() { await deletion.mutateAsync(matrixId); navigate("/matrices-hpn", { replace: true }); }

  return (
    <FullWidthLayout title={matrix?.title ?? "Detalle de matriz HPN"} description="Vista estructurada para revisión humana de hechos, evidencias, normas y relaciones." actions={matrix ? <Inline gap="sm">{!readOnly ? <Button variant="secondary" onClick={() => { update.reset(); setEditing(true); }}>Editar matriz</Button> : null}<Button variant="danger" onClick={() => { deletion.reset(); setDeleting(true); }}>Eliminar</Button></Inline> : undefined} metadata={matrix ? <HpnMatrixStatus matrix={matrix} /> : undefined}>
      <div><Link className={styles.backLink} to="/matrices-hpn">← Volver a matrices</Link></div>
      <ProfessionalReviewNotice />
      {status === "success" ? <AsyncContent status="success">
        {query.data ? <Stack gap="lg">
          {readOnly ? <p className={styles.readOnlyNotice}>El contenido de la matriz está archivado y se presenta en modo de solo lectura. La matriz completa todavía puede eliminarse mediante confirmación explícita.</p> : null}
          <Card as="section" padding="lg"><Stack gap="md"><Heading as="h2">Información de la matriz</Heading>{query.data.matrix.description ? <Text className={styles.sectionDescription}>{query.data.matrix.description}</Text> : <Text variant="secondary">Sin descripción.</Text>}<div className={styles.metadataGrid}><div className={styles.metadataItem}><Text variant="caption">Creada</Text><Text>{formatHpnDate(query.data.matrix.createdAt)}</Text></div><div className={styles.metadataItem}><Text variant="caption">Última actualización</Text><Text>{formatHpnDate(query.data.matrix.updatedAt)}</Text></div></div></Stack></Card>
          <HpnMatrixSummary summary={query.data.validationSummary} />
          <HpnNodeSection matrixId={matrixId} nodes={query.data.nodes} readOnly={readOnly} />
          <HpnRelationSection matrixId={matrixId} nodes={query.data.nodes} relations={query.data.relations} readOnly={readOnly} />
        </Stack> : null}
      </AsyncContent> : <AsyncContent status={status} presentations={{ error: <ErrorState title="Matriz no disponible" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} /> }} />}
      {editing && matrix ? <Modal open title="Editar matriz" description="Las transiciones de estado se validan en el servicio local." onOpenChange={(open) => { if (!open) setEditing(false); }} size="lg" {...modalDismissProps(update.isPending)}><HpnMatrixForm initial={matrix} pending={update.isPending} error={update.error} onCancel={() => setEditing(false)} onSubmit={save} /></Modal> : null}
      <DeleteMatrixDialog publicLabel={matrix?.title ?? "Matriz HPN"} open={deleting} pending={deletion.isPending} error={deletion.error} onClose={() => setDeleting(false)} onConfirm={remove} />
    </FullWidthLayout>
  );
}

export function HpnMatrixDetailPage() {
  const { matrixId } = useParams();
  if (!isHpnId(matrixId)) return <FullWidthLayout title="Matriz no disponible"><ErrorState title="Identificador no válido" message="La ruta solicitada no corresponde a una matriz HPN válida." retryAction={<Link className={styles.backLink} to="/matrices-hpn">Volver a matrices</Link>} /></FullWidthLayout>;
  return <HpnMatrixDetailContent matrixId={matrixId} />;
}
