import type {
  HpnDocumentType,
  HpnId,
  HpnMatrix,
  HpnMatrixDetail,
  HpnMatrixList,
  HpnMatrixStatus,
  HpnNode,
  HpnNodeType,
  HpnRelation,
  HpnRelationType,
  HpnReviewStatus,
  HpnSource,
  HpnSourceStatus,
  HpnValidationSummary,
} from "./hpnMatrices.types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

function invalidResponse(): never {
  throw new Error("HPN_RESPONSE_INVALID");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : invalidResponse();
}

function stringValue(value: unknown, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.trim() === "")) return invalidResponse();
  return value;
}

function nullableString(value: unknown): string | null {
  return value === null ? null : stringValue(value);
}

function integer(value: unknown, minimum = 0): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < minimum) return invalidResponse();
  return value;
}

function booleanValue(value: unknown): boolean {
  return typeof value === "boolean" ? value : invalidResponse();
}

function timestamp(value: unknown): string {
  const result = stringValue(value);
  return Number.isNaN(Date.parse(result)) ? invalidResponse() : result;
}

export function isHpnId(value: unknown): value is HpnId {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function id(value: unknown): HpnId {
  return typeof value === "string" && isHpnId(value) ? value : invalidResponse();
}

export function isHpnMatrixStatus(value: unknown): value is HpnMatrixStatus {
  return value === "draft" || value === "in_review" || value === "reviewed" || value === "archived";
}

function matrixStatus(value: unknown): HpnMatrixStatus {
  if (isHpnMatrixStatus(value)) return value;
  return invalidResponse();
}

export function isHpnNodeType(value: unknown): value is HpnNodeType {
  return value === "fact" || value === "evidence" || value === "norm";
}

function nodeType(value: unknown): HpnNodeType {
  if (isHpnNodeType(value)) return value;
  return invalidResponse();
}

export function isHpnReviewStatus(value: unknown): value is HpnReviewStatus {
  return value === "draft" || value === "reviewed" || value === "rejected";
}

function reviewStatus(value: unknown): HpnReviewStatus {
  if (isHpnReviewStatus(value)) return value;
  return invalidResponse();
}

export function isHpnRelationType(value: unknown): value is HpnRelationType {
  return (
    value === "evidence_supports_fact"
    || value === "evidence_contradicts_fact"
    || value === "norm_applies_to_fact"
    || value === "norm_limits_fact"
  );
}

function relationType(value: unknown): HpnRelationType {
  if (isHpnRelationType(value)) return value;
  return invalidResponse();
}

function sourceStatus(value: unknown): HpnSourceStatus {
  if (value === "valid" || value === "stale" || value === "unavailable") return value;
  return invalidResponse();
}

function documentType(value: unknown): HpnDocumentType {
  if (value === "expediente" || value === "normativa" || value === "jurisprudencia" || value === "otro") return value;
  return invalidResponse();
}

export function parseHpnMatrix(value: unknown): HpnMatrix {
  const item = record(value);
  const createdAt = timestamp(item.created_at);
  const updatedAt = timestamp(item.updated_at);
  if (Date.parse(updatedAt) < Date.parse(createdAt)) return invalidResponse();
  return {
    id: id(item.id),
    title: stringValue(item.title),
    description: nullableString(item.description),
    status: matrixStatus(item.status),
    createdAt,
    updatedAt,
  };
}

function parseSource(value: unknown): HpnSource {
  const item = record(value);
  const startPage = integer(item.start_page, 1);
  const endPage = integer(item.end_page, 1);
  if (endPage < startPage) return invalidResponse();
  return {
    sourceId: id(item.source_id),
    documentId: id(item.document_id),
    documentName: stringValue(item.document_name),
    documentType: documentType(item.document_type),
    chunkIndex: integer(item.chunk_index, 1),
    startPage,
    endPage,
    sourceStatus: sourceStatus(item.source_status),
    linkedAt: timestamp(item.linked_at),
  };
}

export function parseHpnNode(value: unknown): HpnNode {
  const item = record(value);
  if (!Array.isArray(item.sources)) return invalidResponse();
  const sources = item.sources.map(parseSource);
  if (new Set(sources.map((source) => source.sourceId)).size !== sources.length) return invalidResponse();
  const createdAt = timestamp(item.created_at);
  const updatedAt = timestamp(item.updated_at);
  if (Date.parse(updatedAt) < Date.parse(createdAt)) return invalidResponse();
  return {
    id: id(item.id),
    nodeType: nodeType(item.node_type),
    title: stringValue(item.title),
    statement: stringValue(item.statement),
    reviewStatus: reviewStatus(item.review_status),
    displayOrder: integer(item.display_order, 1),
    sources,
    createdAt,
    updatedAt,
  };
}

export function parseHpnRelation(value: unknown): HpnRelation {
  const item = record(value);
  const sourceNodeId = id(item.source_node_id);
  const targetNodeId = id(item.target_node_id);
  if (sourceNodeId === targetNodeId) return invalidResponse();
  const createdAt = timestamp(item.created_at);
  const updatedAt = timestamp(item.updated_at);
  if (Date.parse(updatedAt) < Date.parse(createdAt)) return invalidResponse();
  return {
    id: id(item.id),
    sourceNodeId,
    targetNodeId,
    relationType: relationType(item.relation_type),
    rationale: nullableString(item.rationale),
    reviewStatus: reviewStatus(item.review_status),
    createdAt,
    updatedAt,
  };
}

function parseValidation(value: unknown): HpnValidationSummary {
  const item = record(value);
  return {
    matrixId: id(item.matrix_id),
    validForReview: booleanValue(item.valid_for_review),
    factCount: integer(item.fact_count),
    evidenceCount: integer(item.evidence_count),
    normCount: integer(item.norm_count),
    relationCount: integer(item.relation_count),
    draftNodeCount: integer(item.draft_node_count),
    rejectedNodeCount: integer(item.rejected_node_count),
    draftRelationCount: integer(item.draft_relation_count),
    staleSourceCount: integer(item.stale_source_count),
    unavailableSourceCount: integer(item.unavailable_source_count),
    evidenceWithoutValidSourceCount: integer(item.evidence_without_valid_source_count),
    normWithoutValidSourceCount: integer(item.norm_without_valid_source_count),
  };
}

export function parseHpnMatrixList(value: unknown): HpnMatrixList {
  const response = record(value);
  if (!Array.isArray(response.items)) return invalidResponse();
  const items = response.items.map(parseHpnMatrix);
  if (new Set(items.map((item) => item.id)).size !== items.length) return invalidResponse();
  const pageSize = integer(response.page_size, 1);
  if (pageSize > 100) return invalidResponse();
  return {
    items,
    total: integer(response.total),
    page: integer(response.page, 1),
    pageSize,
  };
}

function validRelationEndpoints(relation: HpnRelation, nodes: ReadonlyMap<HpnId, HpnNode>): boolean {
  const source = nodes.get(relation.sourceNodeId);
  const target = nodes.get(relation.targetNodeId);
  if (!source || !target || target.nodeType !== "fact") return false;
  return relation.relationType.startsWith("evidence_")
    ? source.nodeType === "evidence"
    : source.nodeType === "norm";
}

export function parseHpnMatrixDetail(value: unknown): HpnMatrixDetail {
  const response = record(value);
  if (!Array.isArray(response.nodes) || !Array.isArray(response.relations)) return invalidResponse();
  const matrix = parseHpnMatrix(response.matrix);
  const nodes = response.nodes.map(parseHpnNode);
  const relations = response.relations.map(parseHpnRelation);
  const validationSummary = parseValidation(response.validation_summary);
  if (validationSummary.matrixId !== matrix.id) return invalidResponse();
  const nodeMap = new Map(nodes.map((node) => [node.id, node] as const));
  if (nodeMap.size !== nodes.length) return invalidResponse();
  if (new Set(relations.map((relation) => relation.id)).size !== relations.length) return invalidResponse();
  if (relations.some((relation) => !validRelationEndpoints(relation, nodeMap))) return invalidResponse();
  return { matrix, nodes, relations, validationSummary };
}
