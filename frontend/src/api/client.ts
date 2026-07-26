import { getApiBaseUrl } from "./config";
import {
  ApplicationError,
  RequestCancelledError,
  createConfigurationError,
  createHttpError,
  createNetworkError,
  createTimeoutError,
  isAppError,
  isRequestCancelledError,
} from "./errors";
import type { ApiQuery, ApiRequestOptions, ApiResponse, JsonValue, ResponseParser } from "./types";

const DEFAULT_TIMEOUT_MS = 15_000;
const MIN_TIMEOUT_MS = 100;
const MAX_TIMEOUT_MS = 120_000;

type RequestBody = JsonValue | FormData | undefined;
type AbortSource = "external" | "timeout" | null;

type ResponsePayload =
  | { readonly kind: "empty" }
  | { readonly kind: "json"; readonly value: unknown }
  | { readonly kind: "invalid" };

function isJsonContentType(value: string): boolean {
  const mediaType = value.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json" || mediaType.endsWith("+json");
}

function buildUrl(path: string, query?: ApiQuery): string {
  if (
    !path.startsWith("/")
    || path.includes("//")
    || path.includes("?")
    || path.includes("#")
    || path.includes("\\")
    || path.split("/").includes("..")
  ) {
    throw createConfigurationError();
  }

  let url: URL;
  try {
    url = new URL(`${getApiBaseUrl()}${path}`);
  } catch (error) {
    if (isAppError(error)) throw error;
    throw createConfigurationError();
  }

  if (query) {
    for (const [key, rawValue] of Object.entries(query)) {
      if (rawValue === null || rawValue === undefined) continue;
      if (!/^[a-zA-Z][a-zA-Z0-9_]*$/u.test(key)) throw createConfigurationError();
      const values = Array.isArray(rawValue) ? rawValue : [rawValue];
      for (const value of values) url.searchParams.append(key, String(value));
    }
  }
  return url.toString();
}

async function readPayload(response: Response): Promise<ResponsePayload> {
  if (response.status === 204 || response.status === 205) return { kind: "empty" };
  const rawBody = await response.text();
  if (rawBody === "") return { kind: "empty" };
  const contentType = response.headers.get("content-type") ?? "";
  if (!isJsonContentType(contentType)) return { kind: "invalid" };
  try {
    const value: unknown = JSON.parse(rawBody);
    return { kind: "json", value };
  } catch {
    return { kind: "invalid" };
  }
}

function normalizeTimeout(value: number | undefined): number {
  if (value === undefined) return DEFAULT_TIMEOUT_MS;
  if (!Number.isInteger(value) || value < MIN_TIMEOUT_MS || value > MAX_TIMEOUT_MS) {
    throw createConfigurationError();
  }
  return value;
}

function serializeBody(body: RequestBody): { body?: BodyInit; headers: Headers } {
  const headers = new Headers({ Accept: "application/json" });
  if (body === undefined) return { headers };
  if (body instanceof FormData) return { body, headers };
  headers.set("Content-Type", "application/json");
  return { body: JSON.stringify(body), headers };
}

async function request<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  parser: ResponseParser<T>,
  body: RequestBody,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const timeoutMs = normalizeTimeout(options.timeoutMs);
  let abortSource: AbortSource = null;
  const abortFromCaller = () => {
    if (abortSource === null) abortSource = "external";
    controller.abort();
  };
  const callerSignal = options.signal;
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeoutId = globalThis.setTimeout(() => {
    if (abortSource !== null) return;
    abortSource = "timeout";
    controller.abort();
  }, timeoutMs);

  try {
    const serialized = serializeBody(body);
    const response = await fetch(buildUrl(path, options.query), {
      cache: "no-store",
      credentials: "omit",
      method,
      body: serialized.body,
      headers: serialized.headers,
      signal: controller.signal,
    });
    const payload = await readPayload(response);
    if (!response.ok) {
      throw createHttpError(response.status, payload.kind === "json" ? payload.value : null);
    }
    if (payload.kind === "empty") return { data: null, status: response.status };
    if (payload.kind === "invalid") {
      throw new ApplicationError({
        category: "server",
        code: "API_RESPONSE_INVALID",
        retryable: false,
        severity: "error",
      }, response.status);
    }

    try {
      const data = parser(payload.value);
      if (data === undefined) throw new Error("API_RESPONSE_UNDEFINED");
      return { data, status: response.status };
    } catch {
      throw new ApplicationError({
        category: "server",
        code: "API_RESPONSE_INVALID",
        retryable: false,
        severity: "error",
      }, response.status);
    }
  } catch (error) {
    if (isAppError(error) || isRequestCancelledError(error)) throw error;
    if (abortSource === "timeout") throw createTimeoutError();
    if (abortSource === "external" || controller.signal.aborted) throw new RequestCancelledError();
    if (error instanceof TypeError) throw createNetworkError();
    throw new ApplicationError({ category: "unknown", code: "UNEXPECTED_ERROR", retryable: false, severity: "error" });
  } finally {
    globalThis.clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export const apiClient = {
  get<T>(path: string, parser: ResponseParser<T>, options?: ApiRequestOptions) {
    return request("GET", path, parser, undefined, options);
  },
  post<T>(path: string, body: RequestBody, parser: ResponseParser<T>, options?: ApiRequestOptions) {
    return request("POST", path, parser, body, options);
  },
  put<T>(path: string, body: RequestBody, parser: ResponseParser<T>, options?: ApiRequestOptions) {
    return request("PUT", path, parser, body, options);
  },
  patch<T>(path: string, body: RequestBody, parser: ResponseParser<T>, options?: ApiRequestOptions) {
    return request("PATCH", path, parser, body, options);
  },
  delete<T>(path: string, parser: ResponseParser<T>, options?: ApiRequestOptions) {
    return request("DELETE", path, parser, undefined, options);
  },
};
