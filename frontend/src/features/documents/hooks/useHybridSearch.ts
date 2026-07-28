import { useMutation } from "@tanstack/react-query";
import { searchHybrid } from "../api/hybridSearch.api";
import type { HybridSearchInput } from "../types";
export function useHybridSearch() { return useMutation({ mutationFn: (input: HybridSearchInput) => searchHybrid(input) }); }
