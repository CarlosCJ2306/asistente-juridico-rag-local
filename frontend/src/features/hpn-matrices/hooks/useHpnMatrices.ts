import { useQuery } from "@tanstack/react-query";

import { hpnMatrixKeys, listHpnMatrices } from "../api";

export function useHpnMatrices(page: number, pageSize: number) {
  return useQuery({
    queryKey: hpnMatrixKeys.list(page, pageSize),
    queryFn: ({ signal }) => listHpnMatrices(page, pageSize, signal),
  });
}
