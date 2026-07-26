import type { HealthResponse } from "../types/health";
import { apiClient } from "./client";
import { ApplicationError } from "./errors";

function parseHealthResponse(value: unknown): HealthResponse {
  if (
    typeof value !== "object"
    || value === null
    || !("status" in value)
    || !("service" in value)
    || value.status !== "ok"
    || value.service !== "asistente-juridico-backend"
  ) {
    throw new Error("HEALTH_RESPONSE_INVALID");
  }
  return { status: value.status, service: value.service };
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await apiClient.get("/api/health", parseHealthResponse, { signal });
  if (response.data === null) {
    throw new ApplicationError({ category: "server", code: "API_RESPONSE_INVALID", retryable: false, severity: "error" });
  }
  return response.data;
}
