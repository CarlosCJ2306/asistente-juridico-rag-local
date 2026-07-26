import { useQuery } from "@tanstack/react-query";

import { getHpnMatrix, hpnMatrixKeys } from "../api";
import type { HpnId } from "../types";

export function useHpnMatrix(matrixId: HpnId) {
  return useQuery({
    queryKey: hpnMatrixKeys.detail(matrixId),
    queryFn: ({ signal }) => getHpnMatrix(matrixId, signal),
  });
}
