import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { isRequestCancelledError, toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, Card, EmptyState, ErrorState, Stack, Text } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { DocumentCard, DocumentUploadModal, SemanticIndexPanel } from "../components";
import { useDocuments } from "../hooks";
import type { PublicDocument } from "../types";
import styles from "../documents.module.css";

const PAGE_SIZE = 20;

function queryStatus(isPending: boolean, error: unknown, empty: boolean): AsyncStatus {
  if (isPending || isRequestCancelledError(error)) return "loading";
  if (error) {
    const category = toAppError(error).category;
    if (category === "offline" || category === "network") return "offline";
    if (category === "unauthorized") return "unauthorized";
    if (category === "forbidden") return "forbidden";
    return "error";
  }
  return empty ? "empty" : "success";
}

function Summary({ total, currentPageItems, eligibleItems }: { readonly total: number; readonly currentPageItems: number; readonly eligibleItems: number }) {
  return (
    <Card as="section" className={styles.summaryCard} aria-label="Resumen de biblioteca">
      <div className={styles.summaryGrid}>
        <div className={styles.summaryItem}><Text variant="caption">Documentos registrados</Text><span className={styles.summaryValue}>{total}</span></div>
        <div className={styles.summaryItem}><Text variant="caption">En esta página</Text><span className={styles.summaryValue}>{currentPageItems}</span></div>
        <div className={styles.summaryItem}><Text variant="caption">Disponibles en esta página</Text><span className={styles.summaryValue}>{eligibleItems}</span></div>
      </div>
    </Card>
  );
}

export function DocumentsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const query = useDocuments(page, PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE));
  const status = queryStatus(query.isPending, query.error, query.data?.total === 0);
  const fallbackStatus: Exclude<AsyncStatus, "success"> = status === "success" ? "error" : status;
  const currentItems = query.data?.items ?? [];
  const eligibleItems = currentItems.filter((document) => document.ragEligible).length;

  useEffect(() => {
    if (query.data && page > totalPages) setPage(totalPages);
  }, [page, query.data, totalPages]);

  function openUpload() {
    setUploadOpen(true);
  }

  function handleUploadCompleted(document: PublicDocument) {
    setUploadOpen(false);
    navigate(`/documents/${document.id}`);
  }

  return (
    <ContentLayout title="Biblioteca documental" description="Consulta los metadatos públicos, la procedencia y la disponibilidad de los documentos para recuperación local." actions={<Button onClick={openUpload}>Subir PDF</Button>}>
      <ProfessionalReviewNotice />
      <Text variant="secondary">El procesamiento ocurre localmente. La disponibilidad para consultas se calcula según el estado documental y requiere revisión profesional.</Text>
      {query.isFetching && !query.isPending ? <Text as="p" variant="caption" className={styles.updating} aria-live="polite">Actualizando biblioteca…</Text> : null}
      {status === "success" && query.data ? (
        <AsyncContent status="success">
          <Stack gap="lg">
            <Summary total={query.data.total} currentPageItems={currentItems.length} eligibleItems={eligibleItems} />
            <SemanticIndexPanel />
            {currentItems.length > 0 ? (
              <>
                <ul className={styles.documentList} aria-label="Documentos registrados">
                  {currentItems.map((document) => <li key={document.id}><DocumentCard document={document} /></li>)}
                </ul>
                <nav className={styles.pagination} aria-label="Paginación de documentos">
                  <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Anterior</Button>
                  <Text as="p" variant="secondary" aria-live="polite">Página {page} de {totalPages} · {query.data.total} {query.data.total === 1 ? "documento" : "documentos"}</Text>
                  <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Siguiente</Button>
                </nav>
              </>
            ) : (
              <EmptyState title="No hay documentos en esta página" description="Vuelve a la página anterior para consultar los registros disponibles." action={<Button variant="secondary" onClick={() => setPage((current) => Math.max(1, current - 1))}>Página anterior</Button>} />
            )}
          </Stack>
        </AsyncContent>
      ) : (
        <AsyncContent
          status={fallbackStatus}
          presentations={{
            empty: <EmptyState title="La biblioteca está vacía" description="Aún no hay documentos registrados en esta biblioteca local." action={<Button onClick={openUpload}>Subir PDF</Button>} />,
            error: <ErrorState title="No fue posible cargar la biblioteca" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />,
            offline: <ErrorState title="Backend local no disponible" message="Comprueba la conexión con el backend local y vuelve a intentarlo." retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />,
          }}
        />
      )}
      {uploadOpen ? <DocumentUploadModal open onOpenChange={setUploadOpen} onCompleted={handleUploadCompleted} /> : null}
    </ContentLayout>
  );
}
