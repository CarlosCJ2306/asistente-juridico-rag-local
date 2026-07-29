import { toAppError } from "../../../api";
import type { DocumentType, KnowledgeLayer } from "../../documents";
import { DOCUMENT_TYPE_LABELS, KNOWLEDGE_LAYER_LABELS } from "../../documents";

export function chatErrorMessage(error: unknown): { readonly title: string; readonly message: string; readonly action: "models" | "documents" | null } {
  const appError = toAppError(error);
  if (appError.code.startsWith("RAG_GENERATION") || appError.code.startsWith("RAG_OUTPUT") || appError.code.startsWith("RAG_CITATION")) {
    return { title: "No fue posible generar una respuesta segura", message: "Se encontró evidencia, pero no fue posible generar una respuesta segura.", action: null };
  }
  if (appError.code.startsWith("RAG_LLM")) {
    return { title: "Modelo generativo no disponible", message: "El modelo generativo local no está disponible.", action: "models" };
  }
  if (appError.code.includes("INDEX") || appError.code.includes("EMBEDDING") || appError.code.includes("RETRIEVAL") || appError.code.includes("CHROMA") || appError.code.includes("FTS5")) {
    return { title: "Índice documental no disponible", message: "El índice documental no está disponible para consultas.", action: "documents" };
  }
  if (appError.category === "offline" || appError.category === "network" || appError.category === "timeout") {
    return { title: "Servicio local no disponible", message: "No fue posible conectar con el servicio local.", action: null };
  }
  return { title: "Consulta no completada", message: "No fue posible completar la consulta jurídica.", action: null };
}

export function documentTypeLabel(value: DocumentType): string {
  return DOCUMENT_TYPE_LABELS[value];
}

export function knowledgeLayerLabel(value: KnowledgeLayer): string {
  return KNOWLEDGE_LAYER_LABELS[value].label;
}

export function formatLocalTime(value: Date): string {
  return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(value);
}
