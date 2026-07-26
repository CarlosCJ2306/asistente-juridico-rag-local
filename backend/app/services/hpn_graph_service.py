"""Proyección estructural HPN de solo lectura mediante NetworkX."""

from __future__ import annotations

import importlib
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, TypeAlias
from uuid import UUID

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_error, log_info, log_warning
from app.core.config import settings
from app.core.exceptions import GraphError
from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)
from app.schemas.hpn import HpnMatrixDetail, HpnSourceRead
from app.schemas.hpn_graph import (
    GraphEdge,
    GraphEntityWarningCode,
    GraphMatrix,
    GraphNode,
    GraphSummary,
    GraphWarning,
    HpnGraphProjection,
    SourceStatusSummary,
)
from app.services.hpn_service import (
    HpnService,
    RELATION_ENDPOINT_TYPES as HPN_RELATION_ENDPOINT_TYPES,
)


RELATION_LABELS = MappingProxyType(
    {
        HpnRelationType.EVIDENCE_SUPPORTS_FACT: "apoya",
        HpnRelationType.EVIDENCE_CONTRADICTS_FACT: "contradice",
        HpnRelationType.NORM_APPLIES_TO_FACT: "se vinculó como aplicable a",
        HpnRelationType.NORM_LIMITS_FACT: "limita",
    }
)
RELATION_ENDPOINT_TYPES = MappingProxyType(dict(HPN_RELATION_ENDPOINT_TYPES))

STRUCTURAL_WARNING_CODES = frozenset(
    {
        "GRAPH_EMPTY",
        "GRAPH_DISCONNECTED_COMPONENTS",
        "GRAPH_DIRECTED_CYCLE_DETECTED",
    }
)

SourceStatus: TypeAlias = Literal["valid", "stale", "unavailable"]


@dataclass(frozen=True, slots=True)
class _GraphMatrixInput:
    id: UUID
    title: str
    status: HpnMatrixStatus
    valid_for_review: bool


@dataclass(frozen=True, slots=True)
class _GraphNodeInput:
    id: UUID
    node_type: HpnNodeType
    title: str
    review_status: HpnReviewStatus
    display_order: int
    source_statuses: tuple[SourceStatus, ...]


@dataclass(frozen=True, slots=True)
class _GraphRelationInput:
    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relation_type: HpnRelationType
    review_status: HpnReviewStatus


@dataclass(frozen=True, slots=True)
class _GraphInput:
    matrix: _GraphMatrixInput
    nodes: tuple[_GraphNodeInput, ...]
    relations: tuple[_GraphRelationInput, ...]


class HpnGraphService:
    """Construye una proyección temporal sin persistir grafos ni modificar HPN."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def project(self, matrix_id: UUID) -> HpnGraphProjection:
        """Carga HPN una vez y delega la construcción CPU a un hilo seguro."""

        started = time.perf_counter()
        detail = await HpnService(self.session).detail(matrix_id)
        try:
            if len(detail.nodes) > settings.graph_max_nodes:
                raise GraphError("GRAPH_TOO_LARGE")
            if len(detail.relations) > settings.graph_max_edges:
                raise GraphError("GRAPH_TOO_LARGE")
            graph_input = _materialize_graph_input(detail)
            projection = await anyio.to_thread.run_sync(
                self._build_projection, graph_input
            )
        except GraphError as exc:
            log_warning(
                "Proyección HPN rechazada",
                operation="hpn_graph_project",
                error_code=exc.code,
            )
            raise
        except Exception as exc:
            log_error(
                "Proyección HPN fallida",
                operation="hpn_graph_project",
                error_code="GRAPH_BUILD_FAILED",
            )
            raise GraphError("GRAPH_BUILD_FAILED") from exc
        log_info(
            "Proyección HPN completada",
            operation="hpn_graph_project",
            result="success",
            node_count=projection.summary.node_count,
            edge_count=projection.summary.edge_count,
            warning_count=len(projection.warnings),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return projection

    @staticmethod
    def _build_projection(graph_input: _GraphInput) -> HpnGraphProjection:
        """Construye la proyección desde DTOs sin tocar SQLite ni AsyncSession."""

        networkx = _load_networkx()
        nodes = sorted(
            graph_input.nodes,
            key=lambda node: (node.display_order, node.node_type.value, str(node.id)),
        )
        relations = sorted(
            graph_input.relations,
            key=lambda relation: (
                str(relation.source_node_id),
                str(relation.target_node_id),
                relation.relation_type.value,
                str(relation.id),
            ),
        )
        if (
            len(nodes) > settings.graph_max_nodes
            or len(relations) > settings.graph_max_edges
        ):
            raise GraphError("GRAPH_TOO_LARGE")

        graph: Any = networkx.MultiDiGraph()
        graph_nodes: list[GraphNode] = []
        warnings: list[GraphWarning] = []
        nodes_by_id = {node.id: node for node in nodes}
        if len(nodes_by_id) != len(nodes):
            raise GraphError("GRAPH_RELATION_INVALID")

        for node in nodes:
            source_summary, source_warnings = _source_summary(node.source_statuses)
            flags = _review_warning_flags(node.review_status) + source_warnings
            graph_node = GraphNode(
                id=node.id,
                type=node.node_type,
                label=_safe_label(node.title, node.node_type, node.display_order),
                review_status=node.review_status,
                display_order=node.display_order,
                source_summary=source_summary,
                warning_flags=tuple(sorted(set(flags))),
            )
            graph_nodes.append(graph_node)
            graph.add_node(str(node.id), **graph_node.model_dump(mode="json"))
            warnings.extend(_node_warnings(graph_node))

        graph_edges: list[GraphEdge] = []
        relation_ids: set[UUID] = set()
        for relation in relations:
            source = nodes_by_id.get(relation.source_node_id)
            target = nodes_by_id.get(relation.target_node_id)
            expected_endpoints = RELATION_ENDPOINT_TYPES.get(relation.relation_type)
            if (
                source is None
                or target is None
                or expected_endpoints is None
                or (source.node_type, target.node_type) != expected_endpoints
                or relation.id in relation_ids
            ):
                raise GraphError("GRAPH_RELATION_INVALID")
            label = RELATION_LABELS.get(relation.relation_type)
            if label is None:
                raise GraphError("GRAPH_RELATION_INVALID")
            relation_ids.add(relation.id)
            flags = _review_warning_flags(relation.review_status)
            graph_edge = GraphEdge(
                id=relation.id,
                source=relation.source_node_id,
                target=relation.target_node_id,
                relation_type=relation.relation_type,
                label=label,
                review_status=relation.review_status,
                warning_flags=tuple(sorted(set(flags))),
            )
            graph_edges.append(graph_edge)
            graph.add_edge(
                str(relation.source_node_id),
                str(relation.target_node_id),
                key=str(relation.id),
                **graph_edge.model_dump(mode="json"),
            )
            warnings.extend(_edge_warnings(graph_edge))

        component_count = 0
        isolated_count = 0
        has_cycles = False
        if graph.number_of_nodes() == 0:
            warnings.append(
                GraphWarning(code="GRAPH_EMPTY", entity_type="graph", severity="info")
            )
        else:
            # El resumen conserva siempre el total. GRAPH_MAX_COMPONENTS_DETAIL
            # queda reservado para metadata futura y nunca trunca este conteo.
            component_count = sum(
                1 for _ in networkx.weakly_connected_components(graph)
            )
            isolated_count = sum(graph.degree(node_id) == 0 for node_id in graph.nodes)
            if component_count > 1:
                warnings.append(
                    GraphWarning(
                        code="GRAPH_DISCONNECTED_COMPONENTS",
                        entity_type="graph",
                        severity="warning",
                    )
                )
            has_cycles = not networkx.is_directed_acyclic_graph(graph)
            if has_cycles:
                warnings.append(
                    GraphWarning(
                        code="GRAPH_DIRECTED_CYCLE_DETECTED",
                        entity_type="graph",
                        severity="warning",
                    )
                )

        matrix_warnings: list[GraphWarning] = []
        if graph_input.matrix.status == HpnMatrixStatus.ARCHIVED:
            matrix_warnings.append(
                GraphWarning(
                    code="GRAPH_MATRIX_ARCHIVED",
                    entity_type="matrix",
                    entity_id=graph_input.matrix.id,
                    severity="info",
                )
            )
        warnings.extend(matrix_warnings)
        warnings = _deduplicate_warnings(warnings)
        warnings.sort(
            key=lambda warning: (
                warning.code,
                warning.entity_type,
                str(warning.entity_id or ""),
            )
        )
        summary = GraphSummary(
            node_count=len(graph_nodes),
            edge_count=graph.number_of_edges(),
            isolated_node_count=isolated_count,
            disconnected_components=component_count,
            has_directed_cycles=has_cycles,
            structural_warning_count=sum(
                warning.code in STRUCTURAL_WARNING_CODES for warning in warnings
            ),
        )
        return HpnGraphProjection(
            matrix=GraphMatrix(
                id=graph_input.matrix.id,
                status=graph_input.matrix.status,
                label=_safe_matrix_label(graph_input.matrix.title),
                read_only=graph_input.matrix.status == HpnMatrixStatus.ARCHIVED,
                valid_for_review=graph_input.matrix.valid_for_review,
            ),
            nodes=tuple(graph_nodes),
            edges=tuple(graph_edges),
            warnings=tuple(warnings),
            summary=summary,
        )


def _load_networkx() -> Any:
    """Importa NetworkX solo al construir una proyección."""

    try:
        return importlib.import_module("networkx")
    except ModuleNotFoundError as exc:
        if exc.name == "networkx":
            raise GraphError("GRAPH_DEPENDENCY_NOT_AVAILABLE") from exc
        raise


def _materialize_graph_input(detail: HpnMatrixDetail) -> _GraphInput:
    """Descarta contenido HPN no requerido antes de entrar al hilo de trabajo."""

    return _GraphInput(
        matrix=_GraphMatrixInput(
            id=detail.matrix.id,
            title=detail.matrix.title,
            status=detail.matrix.status,
            valid_for_review=detail.validation_summary.valid_for_review,
        ),
        nodes=tuple(
            _GraphNodeInput(
                id=node.id,
                node_type=node.node_type,
                title=node.title,
                review_status=node.review_status,
                display_order=node.display_order,
                source_statuses=_materialize_source_statuses(node.sources),
            )
            for node in detail.nodes
        ),
        relations=tuple(
            _GraphRelationInput(
                id=relation.id,
                source_node_id=relation.source_node_id,
                target_node_id=relation.target_node_id,
                relation_type=relation.relation_type,
                review_status=relation.review_status,
            )
            for relation in detail.relations
        ),
    )


def _materialize_source_statuses(
    sources: list[HpnSourceRead],
) -> tuple[SourceStatus, ...]:
    """Deduplica por source_id; un duplicado conflictivo invalida la fuente."""

    statuses_by_id: dict[UUID, SourceStatus] = {}
    for source in sources:
        status = source.source_status
        previous = statuses_by_id.get(source.source_id)
        if previous is not None and previous != status:
            raise GraphError("GRAPH_SOURCE_STATUS_INVALID")
        statuses_by_id[source.source_id] = status
    return tuple(
        statuses_by_id[source_id] for source_id in sorted(statuses_by_id, key=str)
    )


def _safe_label(title: str, node_type: HpnNodeType, display_order: int) -> str:
    fallback = {
        HpnNodeType.FACT: "Hecho",
        HpnNodeType.EVIDENCE: "Prueba",
        HpnNodeType.NORM: "Norma",
    }[node_type]
    normalized = unicodedata.normalize("NFC", title)
    without_controls = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    )
    text = _clean_label_text(without_controls)
    if not text:
        text = f"{fallback} {display_order}"
    return text[: settings.graph_max_label_length].rstrip()


def _safe_matrix_label(title: str) -> str:
    normalized = unicodedata.normalize("NFC", title)
    without_controls = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    )
    text = _clean_label_text(without_controls)
    return (text or "Matriz HPN")[: settings.graph_max_label_length].rstrip()


def _clean_label_text(value: str) -> str:
    without_tags = re.sub(r"</?[A-Za-z][^>]*>", " ", value)
    return " ".join(without_tags.replace("<", " ").replace(">", " ").split())


def _source_summary(
    source_statuses: tuple[SourceStatus, ...],
) -> tuple[SourceStatusSummary, tuple[GraphEntityWarningCode, ...]]:
    counts: dict[str, int] = defaultdict(int)
    for status in source_statuses:
        if status not in {"valid", "stale", "unavailable"}:
            raise GraphError("GRAPH_SOURCE_STATUS_INVALID")
        counts[status] += 1
    total = sum(counts.values())
    flags: list[GraphEntityWarningCode] = []
    if counts["stale"]:
        flags.append("GRAPH_SOURCE_STALE")
    if counts["unavailable"]:
        flags.append("GRAPH_SOURCE_UNAVAILABLE")
    return (
        SourceStatusSummary(
            total=total,
            valid=counts["valid"],
            stale=counts["stale"],
            unavailable=counts["unavailable"],
            has_warnings=bool(flags),
        ),
        tuple(flags),
    )


def _review_warning_flags(
    review_status: HpnReviewStatus,
) -> tuple[GraphEntityWarningCode, ...]:
    if review_status == HpnReviewStatus.DRAFT:
        return ("GRAPH_REVIEW_DRAFT",)
    if review_status == HpnReviewStatus.REJECTED:
        return ("GRAPH_REVIEW_REJECTED",)
    return ()


def _deduplicate_warnings(warnings: list[GraphWarning]) -> list[GraphWarning]:
    unique: dict[tuple[str, str, UUID | None, str], GraphWarning] = {}
    for warning in warnings:
        key = (warning.code, warning.entity_type, warning.entity_id, warning.severity)
        unique[key] = warning
    return list(unique.values())


def _node_warnings(node: GraphNode) -> list[GraphWarning]:
    return [
        GraphWarning(
            code=code, entity_type="node", entity_id=node.id, severity="warning"
        )
        for code in node.warning_flags
    ]


def _edge_warnings(edge: GraphEdge) -> list[GraphWarning]:
    return [
        GraphWarning(
            code=code, entity_type="edge", entity_id=edge.id, severity="warning"
        )
        for code in edge.warning_flags
    ]
