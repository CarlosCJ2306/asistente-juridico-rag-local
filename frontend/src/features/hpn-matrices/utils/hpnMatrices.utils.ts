import type { BadgeVariant } from "../../../design-system";
import type {
  HpnDocumentType,
  HpnMatrixStatus,
  HpnNodeType,
  HpnRelationType,
  HpnReviewStatus,
  HpnSourceStatus,
} from "../types";

export const HPN_LIMITS = {
  matrixTitle: 200,
  matrixDescription: 4_000,
  nodeTitle: 200,
  nodeStatement: 8_000,
  relationRationale: 4_000,
} as const;

export const MATRIX_STATUS_LABELS: Readonly<Record<HpnMatrixStatus, string>> = {
  draft: "Borrador",
  in_review: "En revisión",
  reviewed: "Revisada",
  archived: "Archivada",
};

export const NODE_TYPE_LABELS: Readonly<Record<HpnNodeType, string>> = {
  fact: "Hecho",
  evidence: "Evidencia",
  norm: "Norma",
};

export const REVIEW_STATUS_LABELS: Readonly<Record<HpnReviewStatus, string>> = {
  draft: "Borrador",
  reviewed: "Revisado",
  rejected: "Rechazado",
};

export const RELATION_TYPE_LABELS: Readonly<Record<HpnRelationType, string>> = {
  evidence_supports_fact: "La evidencia apoya el hecho",
  evidence_contradicts_fact: "La evidencia contradice el hecho",
  norm_applies_to_fact: "La norma se relaciona con el hecho",
  norm_limits_fact: "La norma limita el hecho",
};

export const SOURCE_STATUS_LABELS: Readonly<Record<HpnSourceStatus, string>> = {
  valid: "Fuente válida",
  stale: "Fuente desactualizada",
  unavailable: "Fuente no disponible",
};

export const DOCUMENT_TYPE_LABELS: Readonly<Record<HpnDocumentType, string>> = {
  expediente: "Expediente",
  normativa: "Normativa",
  jurisprudencia: "Jurisprudencia",
  otro: "Otro",
};

export const MATRIX_STATUS_VARIANTS: Readonly<Record<HpnMatrixStatus, BadgeVariant>> = {
  draft: "neutral",
  in_review: "info",
  reviewed: "success",
  archived: "warning",
};

export const REVIEW_STATUS_VARIANTS: Readonly<Record<HpnReviewStatus, BadgeVariant>> = {
  draft: "neutral",
  reviewed: "success",
  rejected: "danger",
};

export const SOURCE_STATUS_VARIANTS: Readonly<Record<HpnSourceStatus, BadgeVariant>> = {
  valid: "success",
  stale: "warning",
  unavailable: "danger",
};

export function matrixStatusOptions(current: HpnMatrixStatus): readonly HpnMatrixStatus[] {
  if (current === "draft") return ["draft", "in_review", "archived"];
  if (current === "in_review") return ["in_review", "reviewed", "archived"];
  if (current === "reviewed") return ["reviewed", "in_review", "archived"];
  return ["archived"];
}

export function relationSourceType(type: HpnRelationType): HpnNodeType {
  return type.startsWith("evidence_") ? "evidence" : "norm";
}

export function hasUnsafeControlCharacters(value: string): boolean {
  return /\p{C}/u.test(value);
}

export function formatHpnDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Fecha no disponible";
  return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

export function pageRange(startPage: number, endPage: number): string {
  return startPage === endPage ? `Página ${startPage}` : `Páginas ${startPage}–${endPage}`;
}
