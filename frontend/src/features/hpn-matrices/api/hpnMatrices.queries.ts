import type { HpnId } from "../types";

export const hpnMatrixKeys = {
  all: ["hpn-matrices"] as const,
  lists: () => [...hpnMatrixKeys.all, "list"] as const,
  list: (page: number, pageSize: number) => [...hpnMatrixKeys.lists(), { page, pageSize }] as const,
  details: () => [...hpnMatrixKeys.all, "detail"] as const,
  detail: (matrixId: HpnId) => [...hpnMatrixKeys.details(), matrixId] as const,
};
