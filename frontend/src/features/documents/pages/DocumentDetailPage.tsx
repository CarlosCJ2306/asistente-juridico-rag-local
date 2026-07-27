import { Link, useParams } from "react-router-dom";

import { isRequestCancelledError, toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, Card, ErrorState, Heading, Stack, Text } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { ContentLayout } from "../../../layouts";
import { DocumentBadges, DocumentMetadata, DocumentRagAvailability } from "../components";
import { useDocument } from "../hooks";
import { isDocumentId, type DocumentId } from "../types";
import styles from "../documents.module.css";

function queryStatus(isPending: boolean, error: unknown): AsyncStatus {
  if (isPending || isRequestCancelledError(error)) return "loading";
  if (!error) return "success";
  const category = toAppError(error).category;
  if (category === "offline" || category === "network") return "offline";
  if (category === "unauthorized") return "unauthorized";
  if (category === "forbidden") return "forbidden";
  return "error";
}

function DocumentDetail({ documentId }: { readonly documentId: DocumentId }) {
  const query = useDocument(documentId);
  const status = queryStatus(query.isPending, query.error);
  if (status === "success" && query.data) {
    const document = query.data;
    return (
      <ContentLayout title={document.displayName} description="Metadatos públicos y estado actual del documento en la biblioteca local." actions={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>}>
        <ProfessionalReviewNotice />
        <Card as="section">
          <Stack gap="lg">
            <div>
              <Heading as="h2" size="sm">Estado documental</Heading>
              <Text variant="secondary">La biblioteca es de solo lectura: no permite procesar, indexar, revisar ni modificar este documento.</Text>
            </div>
            <DocumentBadges document={document} />
            <DocumentRagAvailability document={document} />
            <DocumentMetadata document={document} detailed />
          </Stack>
        </Card>
      </ContentLayout>
    );
  }
  const fallbackStatus = status === "success" ? "error" : status;
  return (
    <ContentLayout title="Documento no disponible" actions={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>}>
      <AsyncContent status={fallbackStatus} presentations={{
        error: <ErrorState title="No fue posible cargar el documento" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />,
        offline: <ErrorState title="Backend local no disponible" message="Comprueba la conexión con el backend local y vuelve a intentarlo." retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} />,
      }} />
    </ContentLayout>
  );
}

export function DocumentDetailPage() {
  const { documentId } = useParams();
  if (documentId === undefined || !isDocumentId(documentId)) {
    return <ContentLayout title="Documento no disponible"><ErrorState title="Identificador no válido" message="La ruta solicitada no corresponde a un documento disponible." retryAction={<Link className={styles.backLink} to="/documents">Volver a documentos</Link>} /></ContentLayout>;
  }
  return <DocumentDetail documentId={documentId} />;
}
