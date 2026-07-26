import { useEffect, useState } from "react";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, EmptyState, ErrorState, Modal, Stack, Text } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { HpnMatrixCard, HpnMatrixForm } from "../components";
import { useCreateHpnMatrix, useHpnMatrices } from "../hooks";
import type { HpnMatrixCreateInput, HpnMatrixUpdateInput } from "../types";
import { modalDismissProps } from "../utils";
import styles from "../hpnMatrices.module.css";

const PAGE_SIZE = 20;

function queryStatus(isPending: boolean, error: unknown, empty: boolean): AsyncStatus {
  if (isPending) return "loading";
  if (error) {
    const category = toAppError(error).category;
    if (category === "offline" || category === "network") return "offline";
    if (category === "unauthorized") return "unauthorized";
    if (category === "forbidden") return "forbidden";
    return "error";
  }
  return empty ? "empty" : "success";
}

export function HpnMatricesPage() {
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const query = useHpnMatrices(page, PAGE_SIZE);
  const creation = useCreateHpnMatrix();
  const status = queryStatus(query.isPending, query.error, query.data?.items.length === 0);
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE));

  useEffect(() => {
    if (query.data && page > totalPages) setPage(totalPages);
  }, [page, query.data, totalPages]);

  function openCreation() {
    creation.reset();
    setCreating(true);
  }

  async function create(payload: HpnMatrixCreateInput | HpnMatrixUpdateInput) {
    if (!("title" in payload) || payload.title === undefined) return;
    await creation.mutateAsync({ title: payload.title, description: payload.description });
    setCreating(false);
    setPage(1);
  }

  return (
    <ContentLayout title="Matrices HPN" description="Organiza manualmente hechos, evidencias, normas y sus relaciones para revisión profesional." actions={<Button onClick={openCreation}>Crear matriz</Button>}>
      <ProfessionalReviewNotice />
      {status === "success" ? <AsyncContent status="success">
        {query.data ? <Stack gap="md"><ul className={styles.matrixList}>{query.data.items.map((matrix) => <li key={matrix.id}><HpnMatrixCard matrix={matrix} /></li>)}</ul><nav className={styles.pagination} aria-label="Paginación de matrices"><Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Anterior</Button><Text variant="secondary">Página {page} de {totalPages} · {query.data.total} {query.data.total === 1 ? "matriz" : "matrices"}</Text><Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>Siguiente</Button></nav></Stack> : null}
      </AsyncContent> : <AsyncContent status={status} presentations={{
        empty: <EmptyState title="Aún no hay matrices" description="Crea una matriz para comenzar el registro manual de elementos HPN." action={<Button onClick={openCreation}>Crear matriz</Button>} />,
        error: <ErrorState title="No fue posible cargar las matrices" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />,
      }} />}
      {creating ? <Modal open title="Crear matriz HPN" description="La matriz es un instrumento manual y revisable; no produce decisiones jurídicas." onOpenChange={(open) => { if (!open) setCreating(false); }} size="lg" {...modalDismissProps(creation.isPending)}><HpnMatrixForm pending={creation.isPending} error={creation.error} onCancel={() => setCreating(false)} onSubmit={create} /></Modal> : null}
    </ContentLayout>
  );
}
