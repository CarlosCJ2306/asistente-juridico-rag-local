import { Link, useParams } from "react-router-dom";

import { toAppError } from "../../../api";
import { ProfessionalReviewNotice } from "../../../components";
import { AsyncContent, Button, EmptyState, ErrorState, Stack } from "../../../design-system";
import type { AsyncStatus } from "../../../design-system";
import { ContentLayout, FullWidthLayout } from "../../../layouts";
import { isHpnId, type HpnId } from "../../hpn-matrices";
import { legalGraphExportPath } from "../api";
import { LegalGraphFrame, LegalGraphSummary, LegalGraphTextualView } from "../components";
import { useLegalGraph } from "../hooks";
import styles from "../legalNetwork.module.css";

function queryStatus(isPending: boolean, error: unknown): AsyncStatus {
  if (isPending) return "loading";
  if (!error) return "success";
  const category = toAppError(error).category;
  if (category === "offline" || category === "network") return "offline";
  if (category === "unauthorized") return "unauthorized";
  if (category === "forbidden") return "forbidden";
  return "error";
}

function LegalNetworkDetail({ matrixId }: { readonly matrixId: HpnId }) {
  const query = useLegalGraph(matrixId);
  const status = queryStatus(query.isPending, query.error);
  const graph = query.data;
  if (status === "success" && graph) return <FullWidthLayout title={graph.matrix.label} description="Proyección estructural local y de solo lectura para revisión profesional." actions={<Link className={styles.matrixLink} to={`/matrices-hpn/${matrixId}`}>Volver a matriz</Link>}><ProfessionalReviewNotice /><AsyncContent status="success"><Stack gap="lg"><LegalGraphSummary graph={graph} />{graph.nodes.length ? <LegalGraphFrame src={legalGraphExportPath(matrixId)} /> : null}<LegalGraphTextualView graph={graph} /></Stack></AsyncContent></FullWidthLayout>;
  const fallbackStatus = status === "success" ? "error" : status;
  return <FullWidthLayout title="Red jurídica" description="Proyección estructural local y de solo lectura para revisión profesional." actions={<Link className={styles.matrixLink} to={`/matrices-hpn/${matrixId}`}>Volver a matriz</Link>}><ProfessionalReviewNotice /><AsyncContent status={fallbackStatus} presentations={{ error: <ErrorState title="Red jurídica no disponible" message={query.error ? toAppError(query.error).userMessage : "Error controlado."} retryAction={<Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button>} /> }} /></FullWidthLayout>;
}

export function LegalNetworkPage() {
  const { matrixId } = useParams();
  if (matrixId === undefined) return <ContentLayout title="Red jurídica" description="Visualización estructural local de una matriz HPN."><ProfessionalReviewNotice /><EmptyState title="Seleccione una matriz" description="Abra una matriz HPN para acceder a su red jurídica y a su alternativa textual." action={<Link className={styles.matrixLink} to="/matrices-hpn">Ir a matrices HPN</Link>} /></ContentLayout>;
  if (!isHpnId(matrixId)) return <FullWidthLayout title="Red jurídica no disponible"><ErrorState title="Identificador no válido" message="La ruta solicitada no corresponde a una matriz HPN válida." retryAction={<Link className={styles.matrixLink} to="/matrices-hpn">Volver a matrices HPN</Link>} /></FullWidthLayout>;
  return <LegalNetworkDetail matrixId={matrixId} />;
}
