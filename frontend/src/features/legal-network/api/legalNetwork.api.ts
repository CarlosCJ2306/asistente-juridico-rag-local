import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import type { HpnId } from "../../hpn-matrices";
import { parseLegalGraphProjection, type LegalGraphProjection } from "../types";

function graphPath(matrixId: HpnId): string { return `/api/hpn/matrices/${encodeURIComponent(matrixId)}/graph`; }

function requireData<T>(response: ApiResponse<T>): T {
  if (response.status !== 200 || response.data === null) throw createInvalidResponseError();
  return response.data;
}

export async function getLegalGraph(matrixId: HpnId, signal?: AbortSignal): Promise<LegalGraphProjection> {
  return requireData(await apiClient.get(graphPath(matrixId), parseLegalGraphProjection, { signal }));
}

export function legalGraphExportPath(matrixId: HpnId): string { return `${graphPath(matrixId)}/export`; }
