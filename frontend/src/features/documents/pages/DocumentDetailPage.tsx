import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { isRequestCancelledError, toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, Card, ErrorState, Heading, Inline, Modal, Stack, Text } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { DocumentBadges, DocumentMetadata, DocumentRagAvailability } from "../components";
import { useDocument, useDocumentExtraction, useExtractionTotals } from "../hooks";
import { isDocumentId, type DocumentId, type PublicDocument } from "../types";
import { DOCUMENT_STATUS_LABELS, INDEX_STATUS_LABELS } from "../utils";
import styles from "../documents.module.css";

function queryStatus(isPending: boolean, error: unknown): AsyncStatus {
  if (isPending || isRequestCancelledError(error)) return "loading";
  if (!error) return "success";
  const category = toAppError(error).category;
  return category === "offline" || category === "network" ? "offline" : category === "unauthorized" ? "unauthorized" : category === "forbidden" ? "forbidden" : "error";
}

function canExtract(document: PublicDocument): boolean {
  return !document.isExpired && (document.status === "pending_extraction" || document.status === "extraction_failed");
}

function ProcessingProgress({ document }: { readonly document: PublicDocument }) {
  const steps = [
    { label: "Registrado", reached: true },
    { label: "Extrayendo", reached: document.status === "extracting" || document.status === "extracted" },
    { label: "Indexando", reached: document.indexStatus === "indexing" || document.indexStatus === "indexed" },
    { label: "Disponible", reached: document.ragEligible },
  ];
  return <ol className={styles.processingProgress} aria-label="Progreso documental">{steps.map((step) => <li key={step.label} data-reached={step.reached}>{step.label}</li>)}</ol>;
}

function Processing({ document }: { readonly document: PublicDocument }) {
  const [confirming, setConfirming] = useState(false);
  const extraction = useDocumentExtraction(document.id);
  const totals = useExtractionTotals(document.id, document.status === "extracted");
  const allowed = canExtract(document);
  const error = extraction.error ? toAppError(extraction.error) : null;
  const dismissPolicy = extraction.isPending ? { preventClose: true as const, preventCloseReason: "La extracción está en curso." } : {};
  return (
    <Card as="section">
      <Stack gap="md">
        <div><Heading as="h2" size="sm">Procesamiento documental</Heading><Text variant="secondary">La cola local registra, extrae e indexa automáticamente. No usa OCR ni Qwen.</Text></div>
        <ProcessingProgress document={document} />
        <Inline gap="sm"><Text variant="label">Estado: {DOCUMENT_STATUS_LABELS[document.status].label}</Text><Text variant="secondary">{INDEX_STATUS_LABELS[document.indexStatus].label}</Text></Inline>
        {document.status === "extracted" ? <Text variant="secondary">Páginas registradas: {totals.pages.data?.total ?? "consultando"} · Fragmentos generados: {totals.chunks.data?.total ?? "consultando"}. El documento {document.ragEligible ? "está disponible" : "no está disponible"} para consultas.</Text> : null}
        {allowed ? <Button onClick={() => { extraction.reset(); setConfirming(true); }}>Reintentar extracción manual</Button> : <Text variant="secondary">{document.isExpired ? "El documento temporal vencido no se reactiva ni procesa desde esta pantalla." : "La extracción manual no está disponible para el estado actual."}</Text>}
        {error ? <p className={styles.formError} role="alert">{error.code === "PDF_NO_EXTRACTABLE_TEXT" ? "No se encontró texto suficiente. El PDF podría requerir OCR." : "No fue posible extraer contenido utilizable de este documento."}</p> : null}
      </Stack>
      <Modal open={confirming} onOpenChange={setConfirming} title="Reintentar extracción" description="El procesamiento es local y puede tardar según el tamaño del PDF." {...dismissPolicy}>
        <Stack gap="md"><Text variant="secondary">No se realizará OCR ni se cargará Qwen.</Text><Inline gap="sm" justify="end"><Button variant="ghost" disabled={extraction.isPending} onClick={() => setConfirming(false)}>Cancelar</Button><Button loading={extraction.isPending} aria-live="polite" onClick={() => extraction.mutate()}>{extraction.isPending ? "Extrayendo…" : "Reintentar"}</Button></Inline></Stack>
      </Modal>
    </Card>
  );
}

function DocumentDetail({ documentId }: { readonly documentId: DocumentId }) {
  const query = useDocument(documentId);
  const status = queryStatus(query.isPending, query.error);
  if (status === "success" && query.data) {
    const document = query.data;
    return <ContentLayout title={document.displayName} description="Metadatos públicos y estado actual del documento en la biblioteca local." actions={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>}><ProfessionalReviewNotice /><Stack gap="lg"><Card as="section"><Stack gap="lg"><div><Heading as="h2" size="sm">Estado documental</Heading><Text variant="secondary">Metadatos públicos, procedencia y disponibilidad actual.</Text></div><DocumentBadges document={document} /><DocumentRagAvailability document={document} /><DocumentMetadata document={document} detailed /></Stack></Card><Processing document={document} /></Stack></ContentLayout>;
  }
  const fallbackStatus = status === "success" ? "error" : status;
  return <ContentLayout title="Documento no disponible" actions={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>}><AsyncContent status={fallbackStatus} presentations={{ error: <ErrorState title="No fue posible cargar el documento" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />, offline: <ErrorState title="Backend local no disponible" message="Comprueba la conexión con el backend local y vuelve a intentarlo." retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} /> }} /></ContentLayout>;
}

export function DocumentDetailPage() {
  const { documentId } = useParams();
  if (documentId === undefined || !isDocumentId(documentId)) return <ContentLayout title="Documento no disponible"><ErrorState title="Identificador no válido" message="La ruta solicitada no corresponde a un documento disponible." retryAction={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>} /></ContentLayout>;
  return <DocumentDetail documentId={documentId} />;
}
