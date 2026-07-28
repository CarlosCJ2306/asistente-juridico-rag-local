export type ProcessingState =
  | "queued"
  | "detecting"
  | "registering"
  | "extracting"
  | "waiting_for_index"
  | "indexing"
  | "completed"
  | "failed"
  | "quarantined";

export interface ProcessingQueueSummary {
  readonly queued: number;
  readonly processing: number;
  readonly completedRecently: number;
  readonly failed: number;
  readonly quarantined: number;
}
