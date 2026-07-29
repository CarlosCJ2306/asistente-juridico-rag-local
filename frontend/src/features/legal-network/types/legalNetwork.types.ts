import type { HpnId, HpnMatrixStatus, HpnNodeType, HpnRelationType, HpnReviewStatus } from "../../hpn-matrices";

export interface LegalGraphSourceSummary {
  readonly total: number;
  readonly valid: number;
  readonly stale: number;
  readonly unavailable: number;
  readonly hasWarnings: boolean;
}

export interface LegalGraphMatrix {
  readonly id: HpnId;
  readonly status: HpnMatrixStatus;
  readonly label: string;
  readonly readOnly: boolean;
  readonly validForReview: boolean;
}

export interface LegalGraphNode {
  readonly id: HpnId;
  readonly type: HpnNodeType;
  readonly label: string;
  readonly reviewStatus: HpnReviewStatus;
  readonly displayOrder: number;
  readonly sourceSummary: LegalGraphSourceSummary;
  readonly warningFlags: readonly LegalGraphEntityWarningCode[];
}

export interface LegalGraphEdge {
  readonly id: HpnId;
  readonly source: HpnId;
  readonly target: HpnId;
  readonly relationType: HpnRelationType;
  readonly label: string;
  readonly reviewStatus: HpnReviewStatus;
  readonly warningFlags: readonly LegalGraphEntityWarningCode[];
}

export type LegalGraphEntityWarningCode =
  | "GRAPH_REVIEW_DRAFT"
  | "GRAPH_REVIEW_REJECTED"
  | "GRAPH_SOURCE_STALE"
  | "GRAPH_SOURCE_UNAVAILABLE";

export type LegalGraphWarningCode = LegalGraphEntityWarningCode
  | "GRAPH_EMPTY"
  | "GRAPH_DISCONNECTED_COMPONENTS"
  | "GRAPH_DIRECTED_CYCLE_DETECTED"
  | "GRAPH_MATRIX_ARCHIVED";

export interface LegalGraphWarning {
  readonly code: LegalGraphWarningCode;
  readonly entityType: "graph" | "matrix" | "node" | "edge";
  readonly entityId: HpnId | null;
  readonly severity: "info" | "warning";
}

export interface LegalGraphSummary {
  readonly nodeCount: number;
  readonly edgeCount: number;
  readonly isolatedNodeCount: number;
  readonly disconnectedComponents: number;
  readonly hasDirectedCycles: boolean;
  readonly structuralWarningCount: number;
}

export interface LegalGraphProjection {
  readonly matrix: LegalGraphMatrix;
  readonly nodes: readonly LegalGraphNode[];
  readonly edges: readonly LegalGraphEdge[];
  readonly warnings: readonly LegalGraphWarning[];
  readonly summary: LegalGraphSummary;
  readonly requiresProfessionalReview: true;
}
