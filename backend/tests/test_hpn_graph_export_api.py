"""Contrato HTTP de la exportación visual HPN en memoria."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.routes import hpn_graph as graph_route
from app.api.router import api_router
from app.core.exceptions import GraphError, HpnError
from app.database.base import Base
from app.database.models.hpn import HpnMatrixStatus
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app
from app.schemas.hpn_graph import (
    GraphMatrix,
    GraphSummary,
    GraphWarning,
    HpnGraphProjection,
)
from app.visualization.hpn_pyvis_renderer import RenderedGraphHtml
from app.visualization import hpn_pyvis_renderer as renderer_module


def _uuid(value: int) -> UUID:
    return UUID(int=value)


def _projection(*, archived: bool = False) -> HpnGraphProjection:
    status = HpnMatrixStatus.ARCHIVED if archived else HpnMatrixStatus.DRAFT
    return HpnGraphProjection(
        matrix=GraphMatrix(
            id=_uuid(1),
            status=status,
            label="Matriz no exportada",
            read_only=archived,
            valid_for_review=False,
        ),
        nodes=(),
        edges=(),
        warnings=(
            GraphWarning(code="GRAPH_EMPTY", entity_type="graph", severity="info"),
        ),
        summary=GraphSummary(
            node_count=0,
            edge_count=0,
            isolated_node_count=0,
            disconnected_components=0,
            has_directed_cycles=False,
            structural_warning_count=1,
        ),
    )


@pytest.fixture
def export_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert get_db_session not in app.dependency_overrides
    manager = DatabaseSessionManager(tmp_path / "hpn_graph_export_api.db")

    async def create_schema() -> None:
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    state: dict[str, Any] = {
        "projection": _projection(),
        "builder_calls": [],
        "renderer_calls": [],
        "session_yields": 0,
    }

    class StubGraphService:
        def __init__(self, session: object) -> None:
            state["service_session"] = session

        async def project(
            self,
            matrix_id: UUID,
            *,
            request_id: str | None = None,
        ) -> HpnGraphProjection:
            state["builder_calls"].append((matrix_id, request_id))
            error = state.get("builder_error")
            if error is not None:
                raise error
            return state["projection"]

    class StubRenderer:
        async def render(self, projection: HpnGraphProjection) -> RenderedGraphHtml:
            state["renderer_calls"].append(projection)
            error = state.get("renderer_error")
            if error is not None:
                raise error
            mode = "archived" if projection.matrix.read_only else "empty"
            nonce = "synthetic-nonce"
            body = (
                f'<!doctype html><html><style nonce="{nonce}"></style>'
                f'<body>{mode}; requiere revisión profesional</body></html>'
            )
            return RenderedGraphHtml(
                html=body,
                nonce=nonce,
                html_bytes=len(body.encode("utf-8")),
            )

    async def override_session():
        state["session_yields"] += 1
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(graph_route, "HpnGraphService", StubGraphService)
    monkeypatch.setattr(graph_route, "HpnPyvisRenderer", StubRenderer)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, state
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def test_export_api_success_headers_and_single_flow(
    export_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = export_api
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["content-disposition"] == (
        'inline; filename="legal-graph.html"'
    )
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src 'nonce-synthetic-nonce'" in csp
    assert "style-src 'nonce-synthetic-nonce'" in csp
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "*" not in csp
    assert len(state["builder_calls"]) == 1
    assert len(state["renderer_calls"]) == 1
    assert state["renderer_calls"][0] is state["projection"]
    assert state["session_yields"] == 1


def test_export_actual_renderer_csp_nonce_matches_every_inline_block(
    export_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = export_api
    monkeypatch.setattr(graph_route, "HpnPyvisRenderer", renderer_module.HpnPyvisRenderer)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    nonce_match = re.search(r"script-src 'nonce-([^']+)'", csp)
    assert nonce_match is not None
    nonce = nonce_match.group(1)
    assert f"style-src 'nonce-{nonce}'" in csp
    tags = re.findall(r"<(?:script|style)\b([^>]*)>", response.text, re.IGNORECASE)
    assert tags
    assert all(f'nonce="{nonce}"' in attributes for attributes in tags)


def test_export_api_empty_archived_and_json_endpoint_remain_available(
    export_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = export_api
    empty = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert empty.status_code == 200
    assert "empty" in empty.text
    state["projection"] = _projection(archived=True)
    archived = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert archived.status_code == 200
    assert "archived" in archived.text
    graph_json = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    assert graph_json.status_code == 200
    assert graph_json.json()["matrix"]["read_only"] is True


def test_json_endpoint_works_without_pyvis_and_export_returns_503(
    export_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = export_api

    def missing_pyvis(_: str) -> object:
        error = ModuleNotFoundError("pyvis missing")
        error.name = "pyvis"
        raise error

    monkeypatch.setattr(graph_route, "HpnPyvisRenderer", renderer_module.HpnPyvisRenderer)
    monkeypatch.setattr(renderer_module.importlib, "import_module", missing_pyvis)
    graph_json = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph")
    exported = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert graph_json.status_code == 200
    assert exported.status_code == 503
    assert exported.json() == {"detail": "GRAPH_DEPENDENCY_NOT_AVAILABLE"}


def test_internal_pyvis_import_error_is_a_safe_render_failure(
    export_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = export_api

    def broken_pyvis(_: str) -> object:
        raise ImportError("private dependency detail")

    monkeypatch.setattr(graph_route, "HpnPyvisRenderer", renderer_module.HpnPyvisRenderer)
    monkeypatch.setattr(renderer_module.importlib, "import_module", broken_pyvis)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == 500
    assert response.json() == {"detail": "GRAPH_RENDER_FAILED"}
    assert "private dependency detail" not in response.text


@pytest.mark.parametrize(
    ("error", "status_code", "public_code"),
    [
        (HpnError("HPN_MATRIX_NOT_FOUND"), 404, "HPN_MATRIX_NOT_FOUND"),
        (HpnError("HPN_MATRIX_DELETED"), 409, "HPN_MATRIX_DELETED"),
        (GraphError("GRAPH_RELATION_INVALID"), 409, "GRAPH_RELATION_INVALID"),
        (GraphError("GRAPH_SOURCE_STATUS_INVALID"), 409, "GRAPH_SOURCE_STATUS_INVALID"),
        (GraphError("GRAPH_TOO_LARGE"), 413, "GRAPH_TOO_LARGE"),
        (
            GraphError("GRAPH_DEPENDENCY_NOT_AVAILABLE"),
            503,
            "GRAPH_DEPENDENCY_NOT_AVAILABLE",
        ),
        (GraphError("GRAPH_BUILD_FAILED"), 500, "GRAPH_BUILD_FAILED"),
    ],
)
def test_export_api_preserves_safe_builder_errors(
    export_api: tuple[TestClient, dict[str, Any]],
    error: Exception,
    status_code: int,
    public_code: str,
) -> None:
    client, state = export_api
    state["builder_error"] = error
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == status_code
    assert response.json() == {"detail": public_code}
    assert state["renderer_calls"] == []
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("GRAPH_RENDER_FAILED", 500),
        ("GRAPH_TOO_LARGE", 413),
        ("GRAPH_DEPENDENCY_NOT_AVAILABLE", 503),
    ],
)
def test_export_api_maps_renderer_errors_without_partial_html(
    export_api: tuple[TestClient, dict[str, Any]],
    code: str,
    status_code: int,
) -> None:
    client, state = export_api
    state["renderer_error"] = GraphError(code)
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == status_code
    assert response.json() == {"detail": code}
    assert "<!doctype" not in response.text.lower()
    assert "content-security-policy" not in response.headers
    assert "content-disposition" not in response.headers
    assert "nonce-" not in response.text.lower()


def test_export_api_masks_unknown_error_and_logs_only_safe_metadata(
    export_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, state = export_api
    captured: list[dict[str, object]] = []
    private = "__PRIVATE_RENDER_DETAIL__"
    state["renderer_error"] = GraphError(private)
    monkeypatch.setattr(
        graph_route,
        "log_warning",
        lambda message, **context: captured.append(context),
    )
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == 500
    assert response.json() == {"detail": "GRAPH_BUILD_FAILED"}
    serialized = repr(captured)
    assert private not in serialized
    assert str(_uuid(1)) not in serialized
    assert captured[0]["operation"] == "hpn_graph_export_http"
    assert captured[0]["path"] == "/api/hpn/matrices/{matrix_id}/graph/export"
    assert captured[0]["request_id"] is not None


def test_export_success_logging_excludes_ids_html_nonce_and_labels(
    export_api: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = export_api
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        graph_route,
        "log_info",
        lambda message, **context: captured.append(context),
    )
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    assert response.status_code == 200
    serialized = repr(captured)
    assert str(_uuid(1)) not in serialized
    assert "synthetic-nonce" not in serialized
    assert "Matriz no exportada" not in serialized
    assert "<!doctype" not in serialized
    success = captured[0]
    assert success["node_count"] == 0
    assert success["edge_count"] == 0
    assert success["html_bytes"] > 0


def test_export_route_is_registered_once_get_only_without_status(
    export_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, _ = export_api
    routes = [
        route
        for route in graph_route.router.routes
        if isinstance(route, APIRoute)
        and route.path == "/hpn/matrices/{matrix_id}/graph/export"
    ]
    assert len(routes) == 1
    assert routes[0].methods == {"GET"}
    assert (
        sum(
            getattr(route, "original_router", None) is graph_route.router
            for route in api_router.routes
        )
        == 1
    )
    matrix_id = _uuid(1)
    assert client.post(f"/api/hpn/matrices/{matrix_id}/graph/export").status_code == 405
    assert client.get(f"/api/hpn/matrices/{matrix_id}/graph/status").status_code == 404
    invalid = client.get("/api/hpn/matrices/not-a-uuid/graph/export")
    assert invalid.status_code == 422


def test_export_endpoint_leaves_no_html_temporary_or_rendered_files(
    export_api: tuple[TestClient, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = export_api
    working = tmp_path / "working"
    system_temp = tmp_path / "system-temp"
    working.mkdir()
    system_temp.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setenv("TEMP", str(system_temp))
    monkeypatch.setenv("TMP", str(system_temp))
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    response = client.get(f"/api/hpn/matrices/{_uuid(1)}/graph/export")
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert response.status_code == 200
    assert after == before
    assert not tuple(tmp_path.rglob("*.html"))
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_export_openapi_declares_html_read_only_offline_and_errors(
    export_api: tuple[TestClient, dict[str, Any]],
) -> None:
    client, _ = export_api
    operation = client.get("/openapi.json").json()["paths"][
        "/api/hpn/matrices/{matrix_id}/graph/export"
    ]["get"]
    assert set(operation["responses"]) >= {"200", "404", "409", "413", "500", "503"}
    assert "text/html" in operation["responses"]["200"]["content"]
    description = operation["description"].lower()
    assert "offline" in description
    assert "solo lectura" in description
    assert "revisión profesional" in description
    serialized = repr(operation)
    assert str(_uuid(1)) not in serialized
    assert re.search(r"[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-", serialized) is None
