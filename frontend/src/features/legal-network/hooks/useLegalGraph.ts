import { useQuery } from "@tanstack/react-query";

import { getLegalGraph, legalGraphKeys } from "../api";
import type { HpnId } from "../../hpn-matrices/types";

export function useLegalGraph(matrixId: HpnId) {
  return useQuery({ queryKey: legalGraphKeys.detail(matrixId), queryFn: ({ signal }) => getLegalGraph(matrixId, signal) });
}
