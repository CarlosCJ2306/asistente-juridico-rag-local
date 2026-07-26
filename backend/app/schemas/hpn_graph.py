"""Contratos seguros de la proyección estructural HPN."""

from __future__ import annotations

from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)
from app.schemas.hpn import HpnBaseModel


GraphEntityWarningCode: TypeAlias = Literal[
    "GRAPH_REVIEW_DRAFT",
    "GRAPH_REVIEW_REJECTED",
    "GRAPH_SOURCE_STALE",
    "GRAPH_SOURCE_UNAVAILABLE",
]
GraphWarningCode: TypeAlias = Literal[
    "GRAPH_EMPTY",
    "GRAPH_DISCONNECTED_COMPONENTS",
    "GRAPH_DIRECTED_CYCLE_DETECTED",
    "GRAPH_MATRIX_ARCHIVED",
    "GRAPH_REVIEW_DRAFT",
    "GRAPH_REVIEW_REJECTED",
    "GRAPH_SOURCE_STALE",
    "GRAPH_SOURCE_UNAVAILABLE",
]


class GraphBaseModel(HpnBaseModel):
    """Base inmutable para evitar mutaciones entre proyecciones."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)


class SourceStatusSummary(GraphBaseModel):
    """Conteos de fuentes sin revelar referencias documentales."""

    total: int = Field(ge=0)
    valid: int = Field(ge=0)
    stale: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    has_warnings: bool

    @model_validator(mode="after")
    def validate_total(self) -> "SourceStatusSummary":
        if self.total != self.valid + self.stale + self.unavailable:
            raise ValueError("GRAPH_SOURCE_SUMMARY_INVALID")
        if self.has_warnings != bool(self.stale or self.unavailable):
            raise ValueError("GRAPH_SOURCE_SUMMARY_INVALID")
        return self


class GraphMatrix(GraphBaseModel):
    id: UUID
    status: HpnMatrixStatus
    label: str
    read_only: bool
    valid_for_review: bool


class GraphNode(GraphBaseModel):
    id: UUID
    type: HpnNodeType
    label: str
    review_status: HpnReviewStatus
    display_order: int = Field(ge=1)
    source_summary: SourceStatusSummary
    warning_flags: tuple[GraphEntityWarningCode, ...] = Field(default_factory=tuple)


class GraphEdge(GraphBaseModel):
    id: UUID
    source: UUID
    target: UUID
    relation_type: HpnRelationType
    label: str
    review_status: HpnReviewStatus
    warning_flags: tuple[GraphEntityWarningCode, ...] = Field(default_factory=tuple)


class GraphWarning(GraphBaseModel):
    code: GraphWarningCode
    entity_type: Literal["graph", "matrix", "node", "edge"]
    entity_id: UUID | None = None
    severity: Literal["info", "warning"]


class GraphSummary(GraphBaseModel):
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    isolated_node_count: int = Field(ge=0)
    disconnected_components: int = Field(ge=0)
    has_directed_cycles: bool
    structural_warning_count: int = Field(ge=0)


class HpnGraphProjection(GraphBaseModel):
    matrix: GraphMatrix
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    warnings: tuple[GraphWarning, ...]
    summary: GraphSummary
    requires_professional_review: Literal[True] = True
