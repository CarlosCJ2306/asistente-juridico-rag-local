import { apiClient, createInvalidResponseError, type ApiResponse, type JsonValue } from "../../../api";
import {
  parseHpnMatrix,
  parseHpnMatrixDetail,
  parseHpnMatrixList,
  parseHpnNode,
  parseHpnRelation,
  type HpnId,
  type HpnMatrix,
  type HpnMatrixCreateInput,
  type HpnMatrixDetail,
  type HpnMatrixList,
  type HpnMatrixUpdateInput,
  type HpnNode,
  type HpnNodeCreateInput,
  type HpnNodeUpdateInput,
  type HpnRelation,
  type HpnRelationCreateInput,
  type HpnRelationUpdateInput,
} from "../types";

const MATRICES_PATH = "/api/hpn/matrices";

function resourcePath(matrixId: HpnId): string {
  return `${MATRICES_PATH}/${encodeURIComponent(matrixId)}`;
}

function noContent(): null {
  return null;
}

function requireData<T>(response: ApiResponse<T>, expectedStatus: number): T {
  if (response.status !== expectedStatus || response.data === null) throw createInvalidResponseError();
  return response.data;
}

function requireEmpty(response: ApiResponse<null>): void {
  if (response.status !== 204 || response.data !== null) throw createInvalidResponseError();
}

export async function listHpnMatrices(page: number, pageSize: number, signal?: AbortSignal): Promise<HpnMatrixList> {
  const response = await apiClient.get(MATRICES_PATH, parseHpnMatrixList, {
    query: { page, page_size: pageSize },
    signal,
  });
  return requireData(response, 200);
}

export async function getHpnMatrix(matrixId: HpnId, signal?: AbortSignal): Promise<HpnMatrixDetail> {
  const response = await apiClient.get(resourcePath(matrixId), parseHpnMatrixDetail, { signal });
  return requireData(response, 200);
}

export async function createHpnMatrix(payload: HpnMatrixCreateInput, signal?: AbortSignal): Promise<HpnMatrix> {
  const body: Record<string, JsonValue> = { title: payload.title };
  if (payload.description !== undefined) body.description = payload.description;
  const response = await apiClient.post(MATRICES_PATH, body, parseHpnMatrix, { signal });
  return requireData(response, 201);
}

export async function updateHpnMatrix(matrixId: HpnId, payload: HpnMatrixUpdateInput, signal?: AbortSignal): Promise<HpnMatrix> {
  const body: Record<string, JsonValue> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.status !== undefined) body.status = payload.status;
  const response = await apiClient.patch(resourcePath(matrixId), body, parseHpnMatrix, { signal });
  return requireData(response, 200);
}

export async function deleteHpnMatrix(matrixId: HpnId, signal?: AbortSignal): Promise<void> {
  requireEmpty(await apiClient.delete(resourcePath(matrixId), noContent, { signal }));
}

export async function createHpnNode(matrixId: HpnId, payload: HpnNodeCreateInput, signal?: AbortSignal): Promise<HpnNode> {
  const response = await apiClient.post(`${resourcePath(matrixId)}/nodes`, {
    node_type: payload.nodeType,
    title: payload.title,
    statement: payload.statement,
    review_status: payload.reviewStatus,
    display_order: payload.displayOrder,
  }, parseHpnNode, { signal });
  return requireData(response, 201);
}

export async function updateHpnNode(matrixId: HpnId, nodeId: HpnId, payload: HpnNodeUpdateInput, signal?: AbortSignal): Promise<HpnNode> {
  const body: Record<string, JsonValue> = {};
  if (payload.title !== undefined) body.title = payload.title;
  if (payload.statement !== undefined) body.statement = payload.statement;
  if (payload.reviewStatus !== undefined) body.review_status = payload.reviewStatus;
  if (payload.displayOrder !== undefined) body.display_order = payload.displayOrder;
  const response = await apiClient.patch(
    `${resourcePath(matrixId)}/nodes/${encodeURIComponent(nodeId)}`,
    body,
    parseHpnNode,
    { signal },
  );
  return requireData(response, 200);
}

export async function deleteHpnNode(matrixId: HpnId, nodeId: HpnId, signal?: AbortSignal): Promise<void> {
  requireEmpty(await apiClient.delete(`${resourcePath(matrixId)}/nodes/${encodeURIComponent(nodeId)}`, noContent, { signal }));
}

export async function deleteHpnSource(matrixId: HpnId, nodeId: HpnId, sourceId: HpnId, signal?: AbortSignal): Promise<void> {
  requireEmpty(await apiClient.delete(
    `${resourcePath(matrixId)}/nodes/${encodeURIComponent(nodeId)}/sources/${encodeURIComponent(sourceId)}`,
    noContent,
    { signal },
  ));
}

export async function createHpnRelation(matrixId: HpnId, payload: HpnRelationCreateInput, signal?: AbortSignal): Promise<HpnRelation> {
  const body: Record<string, JsonValue> = {
    source_node_id: payload.sourceNodeId,
    target_node_id: payload.targetNodeId,
    relation_type: payload.relationType,
    review_status: payload.reviewStatus,
  };
  if (payload.rationale !== undefined) body.rationale = payload.rationale;
  const response = await apiClient.post(`${resourcePath(matrixId)}/relations`, body, parseHpnRelation, { signal });
  return requireData(response, 201);
}

export async function updateHpnRelation(matrixId: HpnId, relationId: HpnId, payload: HpnRelationUpdateInput, signal?: AbortSignal): Promise<HpnRelation> {
  const body: Record<string, JsonValue> = {};
  if (payload.rationale !== undefined) body.rationale = payload.rationale;
  if (payload.reviewStatus !== undefined) body.review_status = payload.reviewStatus;
  const response = await apiClient.patch(
    `${resourcePath(matrixId)}/relations/${encodeURIComponent(relationId)}`,
    body,
    parseHpnRelation,
    { signal },
  );
  return requireData(response, 200);
}

export async function deleteHpnRelation(matrixId: HpnId, relationId: HpnId, signal?: AbortSignal): Promise<void> {
  requireEmpty(await apiClient.delete(`${resourcePath(matrixId)}/relations/${encodeURIComponent(relationId)}`, noContent, { signal }));
}
