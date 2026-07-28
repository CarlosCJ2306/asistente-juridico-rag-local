import { apiClient, createInvalidResponseError, type ApiResponse } from "../../../api";
import type { ProcessingQueueSummary } from "../types";

function count(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) throw createInvalidResponseError();
  return value;
}

function parseSummary(value: unknown): ProcessingQueueSummary {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw createInvalidResponseError();
  const item = value as Record<string, unknown>;
  return {
    queued: count(item.queued), processing: count(item.processing),
    completedRecently: count(item.completed_recently), failed: count(item.failed),
    quarantined: count(item.quarantined),
  };
}

export async function getProcessingSummary(signal?: AbortSignal): Promise<ProcessingQueueSummary> {
  const response: ApiResponse<ProcessingQueueSummary> = await apiClient.get(
    "/api/documents/processing/summary", parseSummary, { signal },
  );
  if (response.status !== 200 || response.data === null) throw createInvalidResponseError();
  return response.data;
}
