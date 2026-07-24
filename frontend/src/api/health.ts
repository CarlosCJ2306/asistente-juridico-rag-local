import type { HealthResponse } from "../types/health";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`El backend respondió con estado ${response.status}`);
  }

  return (await response.json()) as HealthResponse;
}
