"""Pruebas sintéticas de la proyección NetworkX HPN."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.exceptions import GraphError, HpnError
from app.database.models.document import DocumentType
from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)
from app.schemas.hpn import (
    HpnMatrixDetail,
    HpnMatrixRead,
    HpnNodeRead,
    HpnRelationRead,
    HpnSourceRead,
    HpnValidationSummary,
)
from app.services import hpn_graph_service as graph_module
from app.services.hpn_graph_service import HpnGraphService
from app.schemas.hpn_graph import GraphWarning, HpnGraphProjection, SourceStatusSummary


NOW = datetime(2026, 7, 25, tzinfo=UTC)


def _uuid(value: int) -> UUID:
    return UUID(int=value)


def _source(status: str = "valid", value: int = 90) -> HpnSourceRead:
    return HpnSourceRead(
        source_id=_uuid(value),
        document_id=_uuid(value + 1),
        document_name="fuente.pdf",
        document_type=DocumentType.JURISPRUDENCIA,
        chunk_index=1,
        start_page=1,
        end_page=1,
        source_status=status,  # type: ignore[arg-type]
        linked_at=NOW,
    )


def _node(
    value: int,
    node_type: HpnNodeType,
    *,
    title: str | None = None,
    review_status: HpnReviewStatus = HpnReviewStatus.REVIEWED,
    display_order: int | None = None,
    sources: list[HpnSourceRead] | None = None,
) -> HpnNodeRead:
    return HpnNodeRead(
        id=_uuid(value),
        node_type=node_type,
        title=title if title is not None else f"Nodo {value}",
        statement="Contenido que no debe llegar a la proyección",
        review_status=review_status,
        display_order=display_order or value,
        sources=sources or [],
        created_at=NOW,
        updated_at=NOW,
    )


def _relation(
    value: int,
    source: HpnNodeRead,
    target: HpnNodeRead,
    relation_type: HpnRelationType,
    *,
    review_status: HpnReviewStatus = HpnReviewStatus.REVIEWED,
) -> HpnRelationRead:
    return HpnRelationRead(
        id=_uuid(value),
        source_node_id=source.id,
        target_node_id=target.id,
        relation_type=relation_type,
        rationale="Contenido que no debe llegar a la proyección",
        review_status=review_status,
        created_at=NOW,
        updated_at=NOW,
    )


def _detail(
    *,
    nodes: list[HpnNodeRead] | None = None,
    relations: list[HpnRelationRead] | None = None,
    status: HpnMatrixStatus = HpnMatrixStatus.DRAFT,
) -> HpnMatrixDetail:
    matrix = HpnMatrixRead(
        id=_uuid(1),
        title="Matriz <b>control</b>",
        description=None,
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )
    graph_nodes = nodes or []
    graph_relations = relations or []
    return HpnMatrixDetail(
        matrix=matrix,
        nodes=graph_nodes,
        relations=graph_relations,
        validation_summary=HpnValidationSummary(
            matrix_id=matrix.id,
            valid_for_review=False,
            fact_count=sum(node.node_type == HpnNodeType.FACT for node in graph_nodes),
            evidence_count=sum(
                node.node_type == HpnNodeType.EVIDENCE for node in graph_nodes
            ),
            norm_count=sum(node.node_type == HpnNodeType.NORM for node in graph_nodes),
            relation_count=len(graph_relations),
            draft_node_count=sum(
                node.review_status == HpnReviewStatus.DRAFT for node in graph_nodes
            ),
            rejected_node_count=sum(
                node.review_status == HpnReviewStatus.REJECTED for node in graph_nodes
            ),
            draft_relation_count=sum(
                relation.review_status == HpnReviewStatus.DRAFT
                for relation in graph_relations
            ),
            stale_source_count=0,
            unavailable_source_count=0,
            evidence_without_valid_source_count=0,
            norm_without_valid_source_count=0,
        ),
    )


def _build(detail: HpnMatrixDetail) -> HpnGraphProjection:
    return HpnGraphService._build_projection(
        graph_module._materialize_graph_input(detail)
    )


def test_graph_empty_is_structurally_valid() -> None:
    projection = _build(_detail())
    assert projection.nodes == ()
    assert projection.edges == ()
    assert projection.summary.node_count == 0
    assert projection.summary.disconnected_components == 0
    assert projection.summary.has_directed_cycles is False
    assert [warning.code for warning in projection.warnings] == ["GRAPH_EMPTY"]
    assert projection.requires_professional_review is True


def test_graph_keeps_multiedges_and_safe_attributes() -> None:
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE, sources=[_source()])
    norm = _node(30, HpnNodeType.NORM, sources=[_source(value=100)])
    relations = [
        _relation(40, evidence, fact, HpnRelationType.EVIDENCE_SUPPORTS_FACT),
        _relation(41, evidence, fact, HpnRelationType.EVIDENCE_CONTRADICTS_FACT),
        _relation(42, norm, fact, HpnRelationType.NORM_APPLIES_TO_FACT),
        _relation(43, norm, fact, HpnRelationType.NORM_LIMITS_FACT),
    ]
    projection = _build(_detail(nodes=[fact, evidence, norm], relations=relations))
    assert projection.summary.edge_count == 4
    assert [edge.label for edge in projection.edges] == [
        "contradice",
        "apoya",
        "se vinculó como aplicable a",
        "limita",
    ]
    assert all("statement" not in node.model_dump() for node in projection.nodes)
    assert all("rationale" not in edge.model_dump() for edge in projection.edges)
    assert all("chunk_id" not in node.model_dump() for node in projection.nodes)
    assert all("fingerprint" not in node.model_dump() for node in projection.nodes)


def test_graph_orders_nodes_edges_and_warnings_deterministically() -> None:
    fact = _node(12, HpnNodeType.FACT, display_order=2)
    evidence = _node(
        11, HpnNodeType.EVIDENCE, display_order=1, sources=[_source("stale")]
    )
    relation = _relation(
        31,
        evidence,
        fact,
        HpnRelationType.EVIDENCE_SUPPORTS_FACT,
        review_status=HpnReviewStatus.REJECTED,
    )
    detail = _detail(nodes=[fact, evidence], relations=[relation])
    first = _build(detail)
    second = _build(detail)
    assert [node.id for node in first.nodes] == [evidence.id, fact.id]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [warning.code for warning in first.warnings] == sorted(
        warning.code for warning in first.warnings
    )


def test_graph_exposes_review_and_source_warnings_without_repair() -> None:
    fact = _node(10, HpnNodeType.FACT, review_status=HpnReviewStatus.DRAFT)
    evidence = _node(
        20,
        HpnNodeType.EVIDENCE,
        review_status=HpnReviewStatus.REJECTED,
        sources=[_source("valid"), _source("stale", 100), _source("unavailable", 110)],
    )
    relation = _relation(
        30,
        evidence,
        fact,
        HpnRelationType.EVIDENCE_SUPPORTS_FACT,
        review_status=HpnReviewStatus.REJECTED,
    )
    projection = _build(_detail(nodes=[fact, evidence], relations=[relation]))
    summary = projection.nodes[1].source_summary
    assert (summary.total, summary.valid, summary.stale, summary.unavailable) == (
        3,
        1,
        1,
        1,
    )
    assert summary.has_warnings is True
    assert "GRAPH_REVIEW_REJECTED" in projection.nodes[1].warning_flags
    assert "GRAPH_SOURCE_STALE" in projection.nodes[1].warning_flags
    assert "GRAPH_SOURCE_UNAVAILABLE" in projection.nodes[1].warning_flags
    assert "GRAPH_REVIEW_REJECTED" in projection.edges[0].warning_flags


def test_graph_archived_is_visible_and_read_only() -> None:
    projection = _build(
        _detail(nodes=[_node(10, HpnNodeType.FACT)], status=HpnMatrixStatus.ARCHIVED)
    )
    assert projection.matrix.read_only is True
    assert "GRAPH_MATRIX_ARCHIVED" in [warning.code for warning in projection.warnings]


def test_graph_rejects_invalid_relation_and_source_status() -> None:
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE)
    invalid = _relation(30, fact, evidence, HpnRelationType.EVIDENCE_SUPPORTS_FACT)
    with pytest.raises(GraphError, match="GRAPH_RELATION_INVALID"):
        _build(_detail(nodes=[fact, evidence], relations=[invalid]))

    with pytest.raises(GraphError, match="GRAPH_SOURCE_STATUS_INVALID"):
        graph_module._source_summary(cast(Any, ("unknown",)))


def test_graph_detects_synthetic_cycle_after_relation_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fact = _node(10, HpnNodeType.FACT)
    norm = _node(20, HpnNodeType.NORM)
    relation = _relation(30, norm, fact, HpnRelationType.NORM_LIMITS_FACT)
    networkx = graph_module._load_networkx()
    monkeypatch.setattr(
        graph_module,
        "_load_networkx",
        lambda: SimpleNamespace(
            MultiDiGraph=networkx.MultiDiGraph,
            weakly_connected_components=networkx.weakly_connected_components,
            is_directed_acyclic_graph=lambda graph: False,
        ),
    )
    projection = _build(_detail(nodes=[fact, norm], relations=[relation]))
    assert projection.summary.has_directed_cycles is True
    assert "GRAPH_DIRECTED_CYCLE_DETECTED" in [
        warning.code for warning in projection.warnings
    ]


def test_graph_limits_and_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    node = _node(
        10,
        HpnNodeType.FACT,
        title="<b> Etiqueta\x00 muy larga para verificar el truncamiento seguro </b>",
    )
    monkeypatch.setattr(graph_module.settings, "graph_max_label_length", 12)
    projection = _build(_detail(nodes=[node]))
    assert projection.nodes[0].label == "Etiqueta muy"
    assert "<" not in projection.nodes[0].label

    monkeypatch.setattr(graph_module.settings, "graph_max_nodes", 1)
    with pytest.raises(GraphError, match="GRAPH_TOO_LARGE"):
        _build(_detail(nodes=[node, _node(20, HpnNodeType.NORM)]))

    fact = _node(30, HpnNodeType.FACT)
    evidence = _node(40, HpnNodeType.EVIDENCE)
    relation = _relation(50, evidence, fact, HpnRelationType.EVIDENCE_SUPPORTS_FACT)
    monkeypatch.setattr(graph_module.settings, "graph_max_nodes", 300)
    monkeypatch.setattr(graph_module.settings, "graph_max_edges", 0)
    with pytest.raises(GraphError, match="GRAPH_TOO_LARGE"):
        _build(_detail(nodes=[fact, evidence], relations=[relation]))


@pytest.mark.asyncio
async def test_graph_service_loads_hpn_once_and_uses_thread_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = _detail(nodes=[_node(10, HpnNodeType.FACT)])
    calls = 0

    class FakeHpnService:
        def __init__(self, session: object) -> None:
            del session

        async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
            nonlocal calls
            del matrix_id
            calls += 1
            return detail

    monkeypatch.setattr(graph_module, "HpnService", FakeHpnService)
    service = HpnGraphService(SimpleNamespace())  # type: ignore[arg-type]
    projection = await service.project(_uuid(1))
    assert calls == 1
    assert projection.summary.node_count == 1


def test_graph_dependency_is_lazy_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(name: str) -> object:
        assert name == "networkx"
        raise ModuleNotFoundError("missing", name="networkx")

    monkeypatch.setattr(graph_module.importlib, "import_module", unavailable)
    with pytest.raises(GraphError, match="GRAPH_DEPENDENCY_NOT_AVAILABLE"):
        _build(_detail())


def test_graph_internal_import_error_is_not_dependency_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_dependency(name: str) -> object:
        assert name == "networkx"
        raise ModuleNotFoundError(
            "internal dependency missing", name="internal_dependency"
        )

    monkeypatch.setattr(graph_module.importlib, "import_module", broken_dependency)
    with pytest.raises(ModuleNotFoundError, match="internal dependency missing"):
        graph_module._load_networkx()


@pytest.mark.asyncio
async def test_graph_thread_receives_only_immutable_safe_dtos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = _detail(
        nodes=[
            _node(
                10,
                HpnNodeType.EVIDENCE,
                title="Etiqueta segura",
                sources=[_source()],
            )
        ]
    )
    calls = 0

    class FakeHpnService:
        def __init__(self, session: object) -> None:
            del session

        async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
            nonlocal calls
            del matrix_id
            calls += 1
            return detail

    async def inspect_thread_input(
        function: Any, argument: object
    ) -> HpnGraphProjection:
        assert isinstance(argument, graph_module._GraphInput)
        assert not isinstance(argument, HpnMatrixDetail)
        node = argument.nodes[0]
        assert not hasattr(node, "statement")
        assert not hasattr(node, "sources")
        assert not hasattr(node, "document_id")
        assert not hasattr(node, "chunk_id")
        assert not hasattr(node, "document_name")
        with pytest.raises(FrozenInstanceError):
            setattr(node, "title", "mutado")
        return cast(HpnGraphProjection, function(argument))

    monkeypatch.setattr(graph_module, "HpnService", FakeHpnService)
    monkeypatch.setattr(graph_module.anyio.to_thread, "run_sync", inspect_thread_input)
    projection = await HpnGraphService(SimpleNamespace()).project(_uuid(1))  # type: ignore[arg-type]
    assert calls == 1
    assert projection.summary.node_count == 1


def test_graph_edge_keys_are_public_relation_ids_and_duplicates_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(20, HpnNodeType.EVIDENCE)
    first = _relation(30, evidence, fact, HpnRelationType.EVIDENCE_SUPPORTS_FACT)
    second = _relation(31, evidence, fact, HpnRelationType.EVIDENCE_CONTRADICTS_FACT)
    networkx = graph_module._load_networkx()
    captured: list[Any] = []

    class CapturingMultiDiGraph(  # type: ignore[misc, name-defined, valid-type]
        networkx.MultiDiGraph
    ):
        def __init__(self) -> None:
            super().__init__()
            captured.append(self)

    monkeypatch.setattr(
        graph_module,
        "_load_networkx",
        lambda: SimpleNamespace(
            MultiDiGraph=CapturingMultiDiGraph,
            weakly_connected_components=networkx.weakly_connected_components,
            is_directed_acyclic_graph=networkx.is_directed_acyclic_graph,
        ),
    )
    projection = _build(_detail(nodes=[fact, evidence], relations=[second, first]))
    assert projection.summary.edge_count == 2
    assert sorted(key for _, _, key in captured[0].edges(keys=True)) == [
        str(first.id),
        str(second.id),
    ]
    assert all(
        "statement" not in attributes for _, attributes in captured[0].nodes(data=True)
    )
    assert all(
        "rationale" not in attributes
        for _, _, _, attributes in captured[0].edges(keys=True, data=True)
    )

    duplicate_id = first.model_copy(
        update={"relation_type": HpnRelationType.EVIDENCE_CONTRADICTS_FACT}
    )
    with pytest.raises(GraphError, match="GRAPH_RELATION_INVALID"):
        _build(_detail(nodes=[fact, evidence], relations=[first, duplicate_id]))


def test_graph_contracts_are_closed_consistent_and_immutable() -> None:
    projection = _build(_detail(nodes=[_node(10, HpnNodeType.FACT)]))
    assert isinstance(projection.nodes, tuple)
    assert isinstance(projection.nodes[0].warning_flags, tuple)
    with pytest.raises(ValidationError):
        setattr(projection.matrix, "label", "mutada")
    with pytest.raises(ValidationError):
        GraphWarning(
            code=cast(Any, "GRAPH_UNKNOWN_WARNING"),
            entity_type="graph",
            severity="warning",
        )
    with pytest.raises(ValidationError):
        SourceStatusSummary(
            total=2,
            valid=1,
            stale=0,
            unavailable=0,
            has_warnings=False,
        )


def test_graph_source_deduplication_and_order_are_deterministic() -> None:
    source_a = _source("valid", 90)
    source_b = _source("valid", 100)
    node_with_duplicate = _node(
        10,
        HpnNodeType.EVIDENCE,
        sources=[source_a, source_b, source_a.model_copy(deep=True)],
    )
    summary = _build(_detail(nodes=[node_with_duplicate])).nodes[0].source_summary
    assert (summary.total, summary.valid) == (2, 2)

    reversed_sources = _node(
        10,
        HpnNodeType.EVIDENCE,
        sources=[source_b, source_a],
    )
    assert _build(_detail(nodes=[node_with_duplicate])).model_dump(
        mode="json"
    ) == _build(_detail(nodes=[reversed_sources])).model_dump(mode="json")

    conflicting = source_a.model_copy(update={"source_status": "stale"})
    with pytest.raises(GraphError, match="GRAPH_SOURCE_STATUS_INVALID"):
        graph_module._materialize_graph_input(
            _detail(
                nodes=[
                    _node(
                        10,
                        HpnNodeType.EVIDENCE,
                        sources=[source_a, conflicting],
                    )
                ]
            )
        )


def test_graph_labels_remove_controls_preserve_unicode_and_leave_markdown_as_text() -> (
    None
):
    controls_only = "\x00\x85\u200b\ud800"
    assert graph_module._safe_label(controls_only, HpnNodeType.FACT, 7) == "Hecho 7"
    label = graph_module._safe_label(
        "<b>**Acción y niñez**</b>",
        HpnNodeType.NORM,
        1,
    )
    assert label == "**Acción y niñez**"
    assert len(label) <= graph_module.settings.graph_max_label_length


def test_graph_components_and_structural_warning_count_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _node(
        20,
        HpnNodeType.FACT,
        display_order=1,
        review_status=HpnReviewStatus.DRAFT,
    )
    second = _node(
        10,
        HpnNodeType.EVIDENCE,
        display_order=1,
        sources=[_source("stale")],
    )
    monkeypatch.setattr(graph_module.settings, "graph_max_components_detail", 1)
    projection = _build(_detail(nodes=[first, second]))
    assert [node.id for node in projection.nodes] == [second.id, first.id]
    assert projection.summary.disconnected_components == 2
    assert projection.summary.isolated_node_count == 2
    assert projection.summary.structural_warning_count == 1
    assert len(projection.warnings) > projection.summary.structural_warning_count

    single = _build(_detail(nodes=[first]))
    assert single.summary.disconnected_components == 1
    assert single.summary.isolated_node_count == 1


def test_graph_warning_deduplication_is_stable() -> None:
    warning = GraphWarning(
        code="GRAPH_REVIEW_DRAFT",
        entity_type="node",
        entity_id=_uuid(10),
        severity="warning",
    )
    deduplicated = graph_module._deduplicate_warnings([warning, warning.model_copy()])
    assert deduplicated == [warning]


@pytest.mark.asyncio
async def test_graph_known_errors_and_hpn_errors_are_preserved_without_sensitive_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = _detail(nodes=[_node(10, HpnNodeType.FACT, title="MARCADOR_PRIVADO")])

    class FakeHpnService:
        def __init__(self, session: object) -> None:
            del session

        async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
            del matrix_id
            return detail

    events: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def capture(*args: object, **kwargs: object) -> None:
        events.append((args, kwargs))

    def reject(argument: object) -> HpnGraphProjection:
        del argument
        raise GraphError("GRAPH_RELATION_INVALID")

    monkeypatch.setattr(graph_module, "HpnService", FakeHpnService)
    monkeypatch.setattr(HpnGraphService, "_build_projection", staticmethod(reject))
    monkeypatch.setattr(graph_module, "log_warning", capture)
    with pytest.raises(GraphError, match="GRAPH_RELATION_INVALID"):
        await HpnGraphService(SimpleNamespace()).project(_uuid(1))  # type: ignore[arg-type]
    serialized = repr(events)
    assert "MARCADOR_PRIVADO" not in serialized
    assert str(_uuid(1)) not in serialized
    assert "GRAPH_RELATION_INVALID" in serialized

    class FailingHpnService:
        def __init__(self, session: object) -> None:
            del session

        async def detail(self, matrix_id: UUID) -> HpnMatrixDetail:
            del matrix_id
            raise HpnError("HPN_MATRIX_NOT_FOUND")

    monkeypatch.setattr(graph_module, "HpnService", FailingHpnService)
    with pytest.raises(HpnError, match="HPN_MATRIX_NOT_FOUND"):
        await HpnGraphService(SimpleNamespace()).project(_uuid(1))  # type: ignore[arg-type]
