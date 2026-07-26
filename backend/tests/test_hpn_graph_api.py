"""Contratos HTTP sintéticos de la proyección estructural HPN."""

from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.routes import hpn_graph as graph_route
from app.api.router import api_router
from app.core.exceptions import GraphError, HpnError
from app.database.base import Base
from app.database.models.hpn import (
    HpnMatrixStatus,
    HpnNodeType,
    HpnRelationType,
    HpnReviewStatus,
)
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app
from app.schemas.hpn_graph import (
    GraphEdge,
    GraphMatrix,
    GraphNode,
    GraphSummary,
    GraphWarning,
    HpnGraphProjection,
    SourceStatusSummary,
)
from app.services import hpn_graph_service as graph_service_module
from app.services.hpn_graph_service import HpnGraphService as RealHpnGraphService


_PRIVATE_VALUE_MARKERS = {
    "__PRIVATE_STATEMENT__",
    "__PRIVATE_RATIONALE__",
    "__PRIVATE_DOCUMENT_TEXT__",
    "__PRIVATE_STORAGE_PATH__",
    "__PRIVATE_SQL__",
    "__PRIVATE_TRACEBACK__",
}


def _uuid(value: int) -> UUID:
    return UUID(int=value)


def _projection(
    *,
    status: HpnMatrixStatus = HpnMatrixStatus.DRAFT,
    nodes: tuple[GraphNode, ...] = (),
    edges: tuple[GraphEdge, ...] = (),
    warnings: tuple[GraphWarning, ...] = (),
) -> HpnGraphProjection:
    return HpnGraphProjection(
        matrix=GraphMatrix(
            id=_uuid(1),
            status=status,
            label="Matriz estructural",
            read_only=status == HpnMatrixStatus.ARCHIVED,
            valid_for_review=False,
        ),
        nodes=nodes,
        edges=edges,
        warnings=warnings,
        summary=GraphSummary(
            node_count=len(nodes),
            edge_count=len(edges),
            isolated_node_count=len(nodes) if not edges else 0,
            disconnected_components=0 if not nodes else 1,
            has_directed_cycles=False,
            structural_warning_count=sum(
                warning.code == "GRAPH_EMPTY" for warning in warnings
            ),
        ),
    )


def _node(
    value: int,
    node_type: HpnNodeType,
    *,
    review_status: HpnReviewStatus = HpnReviewStatus.REVIEWED,
    warning_flags: tuple[str, ...] = (),
    source_summary: SourceStatusSummary | None = None,
) -> GraphNode:
    return GraphNode(
        id=_uuid(value),
        type=node_type,
        label=f"Nodo {value}",
        review_status=review_status,
        display_order=value,
        source_summary=source_summary
        or SourceStatusSummary(
            total=0,
            valid=0,
            stale=0,
            unavailable=0,
            has_warnings=False,
        ),
        warning_flags=warning_flags,  # type: ignore[arg-type]
    )


@pytest.fixture
def graph_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert get_db_session not in app.dependency_overrides
    manager = DatabaseSessionManager(tmp_path / "hpn_graph_api.db")

    async def create_schema() -> None:
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    state: dict[str, Any] = {
        "result": _projection(
            warnings=(
                GraphWarning(code="GRAPH_EMPTY", entity_type="graph", severity="info"),
            )
        ),
        "calls": [],
    }

    class StubGraphService:
        def __init__(self, session: object) -> None:
            state["session"] = session

        async def project(
            self,
            matrix_id: UUID,
            *,
            request_id: str | None = None,
        ) -> HpnGraphProjection:
            state["calls"].append((matrix_id, request_id))
            error = state.get("error")
            if error is not None:
                raise error
            return state["result"]

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(graph_route, "HpnGraphService", StubGraphService)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, state
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def _assert_private_terms_absent(value: object) -> None:
    forbidden = {
        "statement",
        "rationale",
        "document_id",
        "chunk_id",
        "source_fingerprint",
        "fingerprint",
        "hash",
        "path",
        "storage_path",
        "stored_name",
        "configuration",
        "internal_config",
        "sql",
        "traceback",
        "html",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key.lower() not in forbidden
            _assert_private_terms_absent(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_private_terms_absent(nested)
    elif isinstance(value, str):
        assert not any(marker in value for marker in _PRIVATE_VALUE_MARKERS)
        assert re.search(r"</?[A-Za-z][^>]*>", value) is None


def test_graph_api_returns_typed_empty_projection_once(
    graph_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = graph_api
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "matrix",
        "nodes",
        "edges",
        "warnings",
        "summary",
        "requires_professional_review",
    }
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["warnings"][0]["code"] == "GRAPH_EMPTY"
    assert isinstance(payload["warnings"], list)
    assert payload["requires_professional_review"] is True
    assert len(state["calls"]) == 1
    _assert_private_terms_absent(payload)


def test_graph_api_preserves_multiedges_states_and_determinism(
    graph_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = graph_api
    fact = _node(10, HpnNodeType.FACT)
    evidence = _node(
        20,
        HpnNodeType.EVIDENCE,
        review_status=HpnReviewStatus.REJECTED,
        warning_flags=("GRAPH_REVIEW_REJECTED",),
        source_summary=SourceStatusSummary(
            total=2,
            valid=0,
            stale=1,
            unavailable=1,
            has_warnings=True,
        ),
    )
    norm = _node(30, HpnNodeType.NORM)
    edges = (
        GraphEdge(
            id=_uuid(40),
            source=evidence.id,
            target=fact.id,
            relation_type=HpnRelationType.EVIDENCE_SUPPORTS_FACT,
            label="apoya",
            review_status=HpnReviewStatus.REVIEWED,
        ),
        GraphEdge(
            id=_uuid(41),
            source=evidence.id,
            target=fact.id,
            relation_type=HpnRelationType.EVIDENCE_CONTRADICTS_FACT,
            label="contradice",
            review_status=HpnReviewStatus.REJECTED,
            warning_flags=("GRAPH_REVIEW_REJECTED",),
        ),
    )
    state["result"] = _projection(
        nodes=(fact, evidence, norm),
        edges=edges,
        warnings=(
            GraphWarning(
                code="GRAPH_REVIEW_REJECTED",
                entity_type="node",
                entity_id=evidence.id,
                severity="warning",
            ),
            GraphWarning(
                code="GRAPH_SOURCE_STALE",
                entity_type="node",
                entity_id=evidence.id,
                severity="warning",
            ),
            GraphWarning(
                code="GRAPH_SOURCE_UNAVAILABLE",
                entity_type="node",
                entity_id=evidence.id,
                severity="warning",
            ),
        ),
    )
    first = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    second = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert {edge["relation_type"] for edge in payload["edges"]} == {
        "evidence_supports_fact",
        "evidence_contradicts_fact",
    }
    assert payload["nodes"][1]["review_status"] == "rejected"
    assert payload["nodes"][1]["source_summary"]["stale"] == 1
    assert payload["nodes"][1]["source_summary"]["unavailable"] == 1
    assert isinstance(payload["edges"][1]["warning_flags"], list)


def test_graph_api_privacy_check_is_recursive_without_label_false_positives() -> None:
    _assert_private_terms_absent(
        {"matrix": {"label": "Ruta procesal"}, "nodes": [{"label": "Hecho normal"}]}
    )
    with pytest.raises(AssertionError):
        _assert_private_terms_absent(
            {"nodes": [{"metadata": {"source_fingerprint": "prohibido"}}]}
        )
    with pytest.raises(AssertionError):
        _assert_private_terms_absent({"nodes": [{"label": "__PRIVATE_STATEMENT__"}]})
    with pytest.raises(AssertionError):
        _assert_private_terms_absent({"nodes": [{"label": "<b>markup</b>"}]})


@pytest.mark.parametrize(
    ("status", "read_only"),
    [
        (HpnMatrixStatus.DRAFT, False),
        (HpnMatrixStatus.IN_REVIEW, False),
        (HpnMatrixStatus.REVIEWED, False),
        (HpnMatrixStatus.ARCHIVED, True),
    ],
)
def test_graph_api_keeps_all_matrix_states_visible(
    graph_api: tuple[TestClient, dict[str, Any]],
    status: HpnMatrixStatus,
    read_only: bool,
) -> None:
    client, state = graph_api
    state["result"] = _projection(status=status)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == 200
    assert response.json()["matrix"] == {
        "id": str(_uuid(1)),
        "status": status.value,
        "label": "Matriz estructural",
        "read_only": read_only,
        "valid_for_review": False,
    }


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("GRAPH_TOO_LARGE", 413),
        ("GRAPH_RELATION_INVALID", 409),
        ("GRAPH_SOURCE_STATUS_INVALID", 409),
        ("GRAPH_DEPENDENCY_NOT_AVAILABLE", 503),
        ("GRAPH_BUILD_FAILED", 500),
    ],
)
def test_graph_api_maps_graph_errors_without_internal_details(
    graph_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    status_code: int,
) -> None:
    client, state = graph_api
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        graph_route,
        "log_warning",
        lambda message, **context: captured.append(context),
    )
    state["error"] = GraphError(code)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == status_code
    assert response.json() == {"detail": code}
    assert "traceback" not in response.text.lower()
    assert str(_uuid(1)) not in repr(captured)
    assert captured[0]["path"] == "/api/hpn/matrices/{matrix_id}/graph"
    assert captured[0]["request_id"] is not None


def test_graph_api_masks_unknown_graph_error_code_and_log(
    graph_api: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = graph_api
    captured: list[dict[str, object]] = []
    marker = "__PRIVATE_UNEXPECTED_GRAPH_ERROR__"
    monkeypatch.setattr(
        graph_route,
        "log_warning",
        lambda message, **context: captured.append(context),
    )
    state["error"] = GraphError(marker)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == 500
    assert response.json() == {"detail": "GRAPH_BUILD_FAILED"}
    assert marker not in response.text
    assert marker not in repr(captured)


def test_graph_api_preserves_hpn_error_and_rejects_invalid_uuid(
    graph_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = graph_api
    state["error"] = HpnError("HPN_MATRIX_DELETED")
    deleted = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert deleted.status_code == 409
    assert deleted.json() == {"detail": "HPN_MATRIX_DELETED"}
    calls_before_invalid = len(state["calls"])
    invalid = client.get("/api/hpn/matrices/no-es-uuid/graph")
    assert invalid.status_code == 422
    assert len(state["calls"]) == calls_before_invalid


def test_graph_api_has_no_status_or_export_and_uses_route_template_logging(
    graph_api: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = graph_api
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        graph_route,
        "log_info",
        lambda message, **context: captured.append(context),
    )
    matrix_id = str(_uuid(1))
    assert client.get(f"/api/hpn/matrices/{matrix_id}/graph").status_code == 200
    assert client.get(f"/api/hpn/matrices/{matrix_id}/graph/status").status_code == 404
    assert client.get(f"/api/hpn/matrices/{matrix_id}/graph/export").status_code == 404
    assert matrix_id not in repr(captured)
    assert any(
        context.get("path") == "/api/hpn/matrices/{matrix_id}/graph"
        for context in captured
    )
    success = captured[0]
    assert success["request_id"] is not None
    assert set(success) == {
        "operation",
        "path",
        "result",
        "node_count",
        "edge_count",
        "warning_count",
        "duration_ms",
        "request_id",
    }


def test_graph_route_is_registered_exactly_once_and_only_as_get() -> None:
    matching = [
        route
        for route in graph_route.router.routes
        if isinstance(route, APIRoute)
        and route.path == "/hpn/matrices/{matrix_id}/graph"
    ]
    assert len(matching) == 1
    assert matching[0].methods == {"GET"}
    assert matching[0].response_model is HpnGraphProjection
    assert matching[0].tags == ["hpn-graph"]
    assert (
        sum(
            getattr(route, "original_router", None) is graph_route.router
            for route in api_router.routes
        )
        == 1
    )
    assert (
        sum(
            getattr(route, "original_router", None) is api_router
            for route in app.routes
        )
        == 1
    )


def test_graph_route_handles_missing_request_id_without_generating_one(
    graph_api: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, state = graph_api
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        graph_route,
        "log_info",
        lambda message, **context: captured.append(context),
    )
    request = SimpleNamespace(state=SimpleNamespace())
    projection = asyncio.run(
        graph_route.get_matrix_graph(  # type: ignore[arg-type]
            _uuid(1), request, object()
        )
    )
    assert projection == state["result"]
    assert captured[0]["request_id"] is None


def test_graph_api_calls_real_graph_service_detail_and_thread_once(
    graph_api: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = graph_api
    counters = {"service": 0, "detail": 0, "thread": 0}

    class StubHpnService:
        def __init__(self, session: object) -> None:
            counters["service"] += 1
            assert session is not None

        async def detail(self, matrix_id: UUID) -> object:
            counters["detail"] += 1
            assert matrix_id == _uuid(1)
            return SimpleNamespace(nodes=(), relations=())

    async def run_sync_once(function: object, argument: object) -> HpnGraphProjection:
        del function, argument
        counters["thread"] += 1
        return state["result"]

    monkeypatch.setattr(graph_route, "HpnGraphService", RealHpnGraphService)
    monkeypatch.setattr(graph_service_module, "HpnService", StubHpnService)
    monkeypatch.setattr(
        graph_service_module,
        "_materialize_graph_input",
        lambda detail: object(),
    )
    monkeypatch.setattr(graph_service_module.anyio.to_thread, "run_sync", run_sync_once)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == 200
    assert counters == {"service": 1, "detail": 1, "thread": 1}


def test_graph_api_hpn_not_found_stops_before_graph_build(
    graph_api: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = graph_api
    counters = {"detail": 0, "thread": 0}

    class MissingHpnService:
        def __init__(self, session: object) -> None:
            assert session is not None

        async def detail(self, matrix_id: UUID) -> object:
            del matrix_id
            counters["detail"] += 1
            raise HpnError("HPN_MATRIX_NOT_FOUND")

    async def forbidden_thread(
        function: object, argument: object
    ) -> HpnGraphProjection:
        del function, argument
        counters["thread"] += 1
        raise AssertionError("El builder no debe ejecutarse")

    monkeypatch.setattr(graph_route, "HpnGraphService", RealHpnGraphService)
    monkeypatch.setattr(graph_service_module, "HpnService", MissingHpnService)
    monkeypatch.setattr(
        graph_service_module.anyio.to_thread,
        "run_sync",
        forbidden_thread,
    )
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert response.status_code == 404
    assert response.json() == {"detail": "HPN_MATRIX_NOT_FOUND"}
    assert counters == {"detail": 1, "thread": 0}


def test_graph_api_openapi_is_typed_and_route_delegates_only_to_graph_service(
    graph_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, _ = graph_api
    operation = client.get("/openapi.json").json()["paths"][
        "/api/hpn/matrices/{matrix_id}/graph"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HpnGraphProjection"
    }
    assert {"404", "409", "413", "500", "503"}.issubset(operation["responses"])
    description = operation["description"].lower()
    assert "proyección estructural" in description
    assert "solo lectura" in description
    assert "profesional" in description
    assert "no representa conclusiones jurídicas automáticas" in description
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/hpn/matrices/{matrix_id}/graph/status" not in paths
    assert "/api/hpn/matrices/{matrix_id}/graph/export" not in paths
    serialized_operation = repr(operation).lower()
    assert "pyvis" not in serialized_operation
    assert "frontend" not in serialized_operation
    assert "html" not in serialized_operation
    source = inspect.getsource(graph_route)
    assert "HpnService" not in source
    assert "networkx" not in source.lower()
