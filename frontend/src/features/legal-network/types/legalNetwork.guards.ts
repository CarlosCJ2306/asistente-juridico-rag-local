import { isHpnId, isHpnMatrixStatus, isHpnNodeType, isHpnRelationType, isHpnReviewStatus, type HpnId } from "../../hpn-matrices/types";
import type { LegalGraphEdge, LegalGraphEntityWarningCode, LegalGraphMatrix, LegalGraphNode, LegalGraphProjection, LegalGraphSourceSummary, LegalGraphSummary, LegalGraphWarning, LegalGraphWarningCode } from "./legalNetwork.types";

function invalidResponse(): never { throw new Error("LEGAL_GRAPH_RESPONSE_INVALID"); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function record(value: unknown): Record<string, unknown> { return isRecord(value) ? value : invalidResponse(); }
function integer(value: unknown): number { return typeof value === "number" && Number.isInteger(value) && Number.isFinite(value) && value >= 0 ? value : invalidResponse(); }
function boolean(value: unknown): boolean { return typeof value === "boolean" ? value : invalidResponse(); }
function text(value: unknown): string { return typeof value === "string" ? value : invalidResponse(); }
function id(value: unknown): HpnId { return isHpnId(value) ? value : invalidResponse(); }

function entityWarning(value: unknown): LegalGraphEntityWarningCode {
  if (value === "GRAPH_REVIEW_DRAFT" || value === "GRAPH_REVIEW_REJECTED" || value === "GRAPH_SOURCE_STALE" || value === "GRAPH_SOURCE_UNAVAILABLE") return value;
  return invalidResponse();
}

function warningCode(value: unknown): LegalGraphWarningCode {
  if (value === "GRAPH_EMPTY" || value === "GRAPH_DISCONNECTED_COMPONENTS" || value === "GRAPH_DIRECTED_CYCLE_DETECTED" || value === "GRAPH_MATRIX_ARCHIVED") return value;
  return entityWarning(value);
}

function sourceSummary(value: unknown): LegalGraphSourceSummary {
  const item = record(value);
  const valid = integer(item.valid);
  const stale = integer(item.stale);
  const unavailable = integer(item.unavailable);
  const total = integer(item.total);
  const hasWarnings = boolean(item.has_warnings);
  if (total !== valid + stale + unavailable || hasWarnings !== Boolean(stale || unavailable)) return invalidResponse();
  return { total, valid, stale, unavailable, hasWarnings };
}

function warningFlags(value: unknown): readonly LegalGraphEntityWarningCode[] {
  if (!Array.isArray(value)) return invalidResponse();
  return value.map(entityWarning);
}

function graphMatrix(value: unknown): LegalGraphMatrix {
  const item = record(value);
  if (!isHpnMatrixStatus(item.status)) return invalidResponse();
  return { id: id(item.id), status: item.status, label: text(item.label), readOnly: boolean(item.read_only), validForReview: boolean(item.valid_for_review) };
}

function graphNode(value: unknown): LegalGraphNode {
  const item = record(value);
  if (!isHpnNodeType(item.type) || !isHpnReviewStatus(item.review_status)) return invalidResponse();
  const displayOrder = integer(item.display_order);
  if (displayOrder < 1) return invalidResponse();
  return { id: id(item.id), type: item.type, label: text(item.label), reviewStatus: item.review_status, displayOrder, sourceSummary: sourceSummary(item.source_summary), warningFlags: warningFlags(item.warning_flags) };
}

function graphEdge(value: unknown): LegalGraphEdge {
  const item = record(value);
  if (!isHpnRelationType(item.relation_type) || !isHpnReviewStatus(item.review_status)) return invalidResponse();
  return { id: id(item.id), source: id(item.source), target: id(item.target), relationType: item.relation_type, label: text(item.label), reviewStatus: item.review_status, warningFlags: warningFlags(item.warning_flags) };
}

function graphWarning(value: unknown): LegalGraphWarning {
  const item = record(value);
  if (item.entity_type !== "graph" && item.entity_type !== "matrix" && item.entity_type !== "node" && item.entity_type !== "edge") return invalidResponse();
  if (item.severity !== "info" && item.severity !== "warning") return invalidResponse();
  return { code: warningCode(item.code), entityType: item.entity_type, entityId: item.entity_id === null ? null : id(item.entity_id), severity: item.severity };
}

function graphSummary(value: unknown): LegalGraphSummary {
  const item = record(value);
  return { nodeCount: integer(item.node_count), edgeCount: integer(item.edge_count), isolatedNodeCount: integer(item.isolated_node_count), disconnectedComponents: integer(item.disconnected_components), hasDirectedCycles: boolean(item.has_directed_cycles), structuralWarningCount: integer(item.structural_warning_count) };
}

export function parseLegalGraphProjection(value: unknown): LegalGraphProjection {
  const item = record(value);
  if (!Array.isArray(item.nodes) || !Array.isArray(item.edges) || !Array.isArray(item.warnings) || item.requires_professional_review !== true) return invalidResponse();
  const nodes = item.nodes.map(graphNode);
  const edges = item.edges.map(graphEdge);
  if (new Set(nodes.map((node) => node.id)).size !== nodes.length || new Set(edges.map((edge) => edge.id)).size !== edges.length) return invalidResponse();
  return { matrix: graphMatrix(item.matrix), nodes, edges, warnings: item.warnings.map(graphWarning), summary: graphSummary(item.summary), requiresProfessionalReview: true };
}
