import { useQuery } from "@tanstack/react-query";

import { documentKeys, listDocuments } from "../api";

export function useDocuments(page: number, pageSize: number) {
  return useQuery({
    queryKey: documentKeys.list(page, pageSize),
    queryFn: ({ signal }) => listDocuments(page, pageSize, signal),
  });
}
