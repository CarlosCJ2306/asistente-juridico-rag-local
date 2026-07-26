export type HpnId = string & { readonly __hpnId: unique symbol };

export type HpnMatrixStatus = "draft" | "in_review" | "reviewed" | "archived";
export type HpnNodeType = "fact" | "evidence" | "norm";
export type HpnReviewStatus = "draft" | "reviewed" | "rejected";
export type HpnRelationType =
  | "evidence_supports_fact"
  | "evidence_contradicts_fact"
  | "norm_applies_to_fact"
  | "norm_limits_fact";
export type HpnSourceStatus = "valid" | "stale" | "unavailable";
export type HpnDocumentType = "expediente" | "normativa" | "jurisprudencia" | "otro";

export interface HpnMatrix {
  readonly id: HpnId;
  readonly title: string;
  readonly description: string | null;
  readonly status: HpnMatrixStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface HpnMatrixList {
  readonly items: readonly HpnMatrix[];
  readonly total: number;
  readonly page: number;
  readonly pageSize: number;
}

export interface HpnSource {
  readonly sourceId: HpnId;
  readonly documentId: HpnId;
  readonly documentName: string;
  readonly documentType: HpnDocumentType;
  readonly chunkIndex: number;
  readonly startPage: number;
  readonly endPage: number;
  readonly sourceStatus: HpnSourceStatus;
  readonly linkedAt: string;
}

export interface HpnNode {
  readonly id: HpnId;
  readonly nodeType: HpnNodeType;
  readonly title: string;
  readonly statement: string;
  readonly reviewStatus: HpnReviewStatus;
  readonly displayOrder: number;
  readonly sources: readonly HpnSource[];
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface HpnRelation {
  readonly id: HpnId;
  readonly sourceNodeId: HpnId;
  readonly targetNodeId: HpnId;
  readonly relationType: HpnRelationType;
  readonly rationale: string | null;
  readonly reviewStatus: HpnReviewStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface HpnValidationSummary {
  readonly matrixId: HpnId;
  readonly validForReview: boolean;
  readonly factCount: number;
  readonly evidenceCount: number;
  readonly normCount: number;
  readonly relationCount: number;
  readonly draftNodeCount: number;
  readonly rejectedNodeCount: number;
  readonly draftRelationCount: number;
  readonly staleSourceCount: number;
  readonly unavailableSourceCount: number;
  readonly evidenceWithoutValidSourceCount: number;
  readonly normWithoutValidSourceCount: number;
}

export interface HpnMatrixDetail {
  readonly matrix: HpnMatrix;
  readonly nodes: readonly HpnNode[];
  readonly relations: readonly HpnRelation[];
  readonly validationSummary: HpnValidationSummary;
}

export type HpnMatrixCreateInput = {
  readonly title: string;
  readonly description?: string | null;
};

export type HpnMatrixUpdateInput = {
  readonly title?: string;
  readonly description?: string | null;
  readonly status?: HpnMatrixStatus;
};

export type HpnNodeCreateInput = {
  readonly nodeType: HpnNodeType;
  readonly title: string;
  readonly statement: string;
  readonly reviewStatus: HpnReviewStatus;
  readonly displayOrder: number;
};

export type HpnNodeUpdateInput = {
  readonly title?: string;
  readonly statement?: string;
  readonly reviewStatus?: HpnReviewStatus;
  readonly displayOrder?: number;
};

export type HpnRelationCreateInput = {
  readonly sourceNodeId: HpnId;
  readonly targetNodeId: HpnId;
  readonly relationType: HpnRelationType;
  readonly rationale?: string | null;
  readonly reviewStatus: HpnReviewStatus;
};

export type HpnRelationUpdateInput = {
  readonly rationale?: string | null;
  readonly reviewStatus?: HpnReviewStatus;
};
