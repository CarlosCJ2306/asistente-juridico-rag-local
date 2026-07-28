import { useQuery } from "@tanstack/react-query";

import { getProcessingSummary } from "../api/documentProcessing.api";

export function useDocumentProcessing() {
  return useQuery({
    queryKey: ["documents", "processing", "summary"],
    queryFn: ({ signal }) => getProcessingSummary(signal),
    refetchInterval: 3_000,
  });
}
