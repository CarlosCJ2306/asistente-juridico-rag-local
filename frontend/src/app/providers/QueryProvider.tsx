import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";

import { isAppError, isRequestCancelledError } from "../../api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry(failureCount, error) {
        if (isRequestCancelledError(error)) return false;
        return isAppError(error) && error.retryable && failureCount < 1;
      },
      staleTime: 30_000,
    },
    mutations: { retry: false },
  },
});

export function QueryProvider({ children }: PropsWithChildren) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
