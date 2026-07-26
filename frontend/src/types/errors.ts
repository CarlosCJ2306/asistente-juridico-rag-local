export type AppErrorCategory =
  | "validation"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "too_large"
  | "unavailable"
  | "server"
  | "network"
  | "offline"
  | "timeout"
  | "unknown";

export type AppErrorSeverity = "info" | "warning" | "error";

export interface AppError {
  readonly code: string;
  readonly category: AppErrorCategory;
  readonly userMessage: string;
  readonly status?: number;
  readonly retryable: boolean;
  readonly severity: AppErrorSeverity;
}
