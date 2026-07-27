import type { BadgeVariant } from "../../../design-system";
import type {
  DocumentStatus,
  DocumentType,
  IndexStatus,
  KnowledgeLayer,
  LegalValidityStatus,
  RagEligibilityReason,
  ReviewStatus,
  SourceKind,
} from "../types";

type LabelledStatus = { readonly label: string; readonly variant: BadgeVariant };

export const KNOWLEDGE_LAYER_LABELS: Record<KnowledgeLayer, LabelledStatus> = {
  managed_corpus: { label: "Corpus administrado", variant: "info" },
  private_library: { label: "Biblioteca privada", variant: "neutral" },
  temporary: { label: "Temporal", variant: "warning" },
  web_verified: { label: "Fuente web verificada", variant: "info" },
  global_candidate: { label: "Candidato al corpus", variant: "warning" },
};

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  expediente: "Expediente",
  normativa: "Normativa",
  jurisprudencia: "Jurisprudencia",
  otro: "Otro",
};

export const SOURCE_KIND_LABELS: Record<SourceKind, string> = {
  local_upload: "Carga local",
  managed_import: "Importación administrada",
  web_import: "Importación web",
};

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, LabelledStatus> = {
  registered: { label: "Registrado", variant: "neutral" },
  stored: { label: "Almacenado", variant: "neutral" },
  pending_extraction: { label: "Pendiente de extracción", variant: "warning" },
  extracting: { label: "Extrayendo", variant: "info" },
  extracted: { label: "Extraído", variant: "success" },
  extraction_failed: { label: "Extracción con error", variant: "danger" },
  failed: { label: "Procesamiento con error", variant: "danger" },
  archived: { label: "Archivado", variant: "warning" },
};

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, LabelledStatus> = {
  not_required: { label: "Revisión no requerida", variant: "neutral" },
  pending: { label: "Revisión pendiente", variant: "warning" },
  approved: { label: "Revisado y aprobado", variant: "success" },
  rejected: { label: "Revisión rechazada", variant: "danger" },
  archived: { label: "Revisión archivada", variant: "warning" },
};

export const LEGAL_VALIDITY_LABELS: Record<LegalValidityStatus, LabelledStatus> = {
  unknown: { label: "Vigencia sin definir", variant: "neutral" },
  current: { label: "Vigencia actual", variant: "success" },
  superseded: { label: "Versión sustituida", variant: "warning" },
  repealed: { label: "Vigencia derogada", variant: "danger" },
  expired: { label: "Vigencia expirada", variant: "danger" },
};

export const INDEX_STATUS_LABELS: Record<IndexStatus, LabelledStatus> = {
  not_requested: { label: "Indexación no solicitada", variant: "neutral" },
  pending: { label: "Indexación pendiente", variant: "warning" },
  indexing: { label: "Indexando", variant: "info" },
  indexed: { label: "Indexado", variant: "success" },
  failed: { label: "Indexación con error", variant: "danger" },
  excluded: { label: "Excluido de indexación", variant: "warning" },
};

const RAG_REASON_LABELS: Record<RagEligibilityReason, string> = {
  document_deleted: "El documento ya no está disponible.",
  document_archived: "El documento está archivado.",
  extraction_incomplete: "El procesamiento documental aún no está completo.",
  review_pending: "La revisión documental está pendiente.",
  review_rejected: "La revisión documental fue rechazada.",
  legal_validity_not_allowed: "La vigencia declarada no permite consultas.",
  temporary_expiration_missing: "El documento temporal requiere una fecha de expiración.",
  temporary_expired: "El documento temporal expiró.",
  expiration_not_allowed: "La expiración actual no permite consultas.",
  layer_not_rag_eligible: "La capa documental no permite consultas.",
  index_not_ready: "La indexación aún no está lista.",
};

export function ragAvailability(reasons: readonly RagEligibilityReason[], eligible: boolean): { readonly label: string; readonly variant: BadgeVariant; readonly messages: readonly string[] } {
  if (eligible) return { label: "Disponible para consultas", variant: "success", messages: [] };
  const messages = reasons.map((reason) => RAG_REASON_LABELS[reason]).filter((message, index, values) => values.indexOf(message) === index);
  return {
    label: "No disponible para consultas",
    variant: "warning",
    messages: messages.length > 0 ? messages : ["No está disponible para consultas en su estado actual."],
  };
}

export function formatDocumentDate(value: string | null): string {
  if (value === null) return "No disponible";
  return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function formatDocumentSize(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
