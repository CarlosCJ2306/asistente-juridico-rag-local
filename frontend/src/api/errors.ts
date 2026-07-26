import type { AppError, AppErrorCategory, AppErrorSeverity } from "../types/errors";
import { ERROR_MESSAGES } from "../utils/errorMessages";

const SAFE_BACKEND_CODE = /^[A-Z][A-Z0-9_]{2,63}$/u;

interface ErrorDefinition {
  readonly category: AppErrorCategory;
  readonly code: string;
  readonly retryable: boolean;
  readonly severity: AppErrorSeverity;
}

export class ApplicationError extends Error implements AppError {
  readonly category: AppErrorCategory;
  readonly code: string;
  readonly retryable: boolean;
  readonly severity: AppErrorSeverity;
  readonly status?: number;
  readonly userMessage: string;

  constructor(definition: ErrorDefinition, status?: number) {
    super(definition.code);
    this.name = "ApplicationError";
    this.category = definition.category;
    this.code = definition.code;
    this.retryable = definition.retryable;
    this.severity = definition.severity;
    this.status = status;
    this.userMessage = ERROR_MESSAGES[definition.category];
  }
}

export class RequestCancelledError extends Error {
  readonly cancelled = true;

  constructor() {
    super("REQUEST_CANCELLED");
    this.name = "RequestCancelledError";
  }
}

export function isAppError(value: unknown): value is ApplicationError {
  return value instanceof ApplicationError;
}

export function isRequestCancelledError(value: unknown): value is RequestCancelledError {
  return value instanceof RequestCancelledError;
}

export function createTimeoutError(): ApplicationError {
  return new ApplicationError({ category: "timeout", code: "REQUEST_TIMEOUT", retryable: true, severity: "warning" });
}

export function createNetworkError(): ApplicationError {
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  return new ApplicationError({
    category: offline ? "offline" : "network",
    code: offline ? "BROWSER_OFFLINE" : "NETWORK_ERROR",
    retryable: true,
    severity: "warning",
  });
}

export function createConfigurationError(): ApplicationError {
  return new ApplicationError({ category: "unavailable", code: "API_CONFIGURATION_INVALID", retryable: false, severity: "error" });
}

function statusDefinition(status: number): ErrorDefinition {
  if (status === 400 || status === 422) return { category: "validation", code: "REQUEST_VALIDATION_ERROR", retryable: false, severity: "warning" };
  if (status === 401) return { category: "unauthorized", code: "REQUEST_UNAUTHORIZED", retryable: false, severity: "warning" };
  if (status === 403) return { category: "forbidden", code: "REQUEST_FORBIDDEN", retryable: false, severity: "warning" };
  if (status === 404) return { category: "not_found", code: "RESOURCE_NOT_FOUND", retryable: false, severity: "warning" };
  if (status === 409) return { category: "conflict", code: "REQUEST_CONFLICT", retryable: false, severity: "warning" };
  if (status === 413) return { category: "too_large", code: "REQUEST_TOO_LARGE", retryable: false, severity: "warning" };
  if (status === 503) return { category: "unavailable", code: "SERVICE_UNAVAILABLE", retryable: true, severity: "warning" };
  if (status >= 500) return { category: "server", code: "SERVER_ERROR", retryable: true, severity: "error" };
  return { category: "unknown", code: "REQUEST_ERROR", retryable: false, severity: "error" };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function extractSafeBackendCode(value: unknown): string | undefined {
  const body = isRecord(value) ? value : undefined;
  const detail = isRecord(body?.detail) ? body.detail : undefined;
  const candidate = body?.error_code ?? detail?.error_code;
  return typeof candidate === "string" && SAFE_BACKEND_CODE.test(candidate) ? candidate : undefined;
}

export function createHttpError(status: number, body: unknown): ApplicationError {
  const definition = statusDefinition(status);
  const safeBackendCode = extractSafeBackendCode(body);
  return new ApplicationError({ ...definition, code: safeBackendCode ?? definition.code }, status);
}

export function toAppError(value: unknown): AppError {
  if (isAppError(value)) return value;
  return new ApplicationError({ category: "unknown", code: "UNEXPECTED_ERROR", retryable: false, severity: "error" });
}
