"""Contratos HTTP HPN con SQLite temporal."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app


@pytest.fixture
def hpn_client(tmp_path: Path):
    manager = DatabaseSessionManager(tmp_path / "hpn_api.db")

    async def create_schema() -> None:
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def test_hpn_matrix_crud_and_validation_contract(hpn_client: TestClient) -> None:
    created = hpn_client.post(
        "/api/hpn/matrices", json={"title": "Matriz sintética", "description": "Manual"}
    )
    assert created.status_code == 201
    matrix_id = created.json()["id"]
    listed = hpn_client.get("/api/hpn/matrices")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    detail = hpn_client.get(f"/api/hpn/matrices/{matrix_id}")
    assert detail.status_code == 200
    assert set(detail.json()) == {"matrix", "nodes", "relations", "validation_summary"}
    validation = hpn_client.get(f"/api/hpn/matrices/{matrix_id}/validation")
    assert validation.status_code == 200
    assert validation.json()["valid_for_review"] is False
    assert "title" not in validation.json()
    review = hpn_client.patch(f"/api/hpn/matrices/{matrix_id}", json={"status": "reviewed"})
    assert review.status_code == 409
    assert review.json()["detail"] == "HPN_REVIEW_INCOMPLETE"
    deleted = hpn_client.delete(f"/api/hpn/matrices/{matrix_id}")
    assert deleted.status_code == 204
    deleted_read = hpn_client.get(f"/api/hpn/matrices/{matrix_id}")
    assert deleted_read.status_code == 409
    assert deleted_read.json()["detail"] == "HPN_MATRIX_DELETED"


def test_hpn_api_rejects_invalid_payloads_and_preserves_old_routes(hpn_client: TestClient) -> None:
    invalid = hpn_client.post("/api/hpn/matrices", json={"title": " ", "unknown": "x"})
    assert invalid.status_code == 422
    missing = hpn_client.get("/api/hpn/matrices/00000000-0000-0000-0000-000000000001")
    assert missing.status_code == 404
    assert hpn_client.get("/api/health").status_code == 200


def test_hpn_node_relation_and_soft_delete_endpoints(hpn_client: TestClient) -> None:
    matrix_id = hpn_client.post("/api/hpn/matrices", json={"title": "M"}).json()["id"]
    fact = hpn_client.post(
        f"/api/hpn/matrices/{matrix_id}/nodes",
        json={
            "node_type": "fact",
            "title": "Hecho",
            "statement": "Manual",
            "review_status": "reviewed",
            "display_order": 1,
        },
    )
    evidence = hpn_client.post(
        f"/api/hpn/matrices/{matrix_id}/nodes",
        json={
            "node_type": "evidence",
            "title": "Prueba",
            "statement": "Manual",
            "display_order": 2,
        },
    )
    assert fact.status_code == evidence.status_code == 201
    relation = hpn_client.post(
        f"/api/hpn/matrices/{matrix_id}/relations",
        json={
            "source_node_id": evidence.json()["id"],
            "target_node_id": fact.json()["id"],
            "relation_type": "evidence_supports_fact",
        },
    )
    assert relation.status_code == 201
    assert hpn_client.delete(
        f"/api/hpn/matrices/{matrix_id}/relations/{relation.json()['id']}"
    ).status_code == 204
    assert hpn_client.delete(
        f"/api/hpn/matrices/{matrix_id}/nodes/{evidence.json()['id']}"
    ).status_code == 204


def test_hpn_request_logs_use_route_templates_without_resource_ids(
    hpn_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.core.middleware.log_info",
        lambda message, **context: captured.append(context),
    )
    matrix_id = hpn_client.post("/api/hpn/matrices", json={"title": "M"}).json()["id"]
    assert hpn_client.get(f"/api/hpn/matrices/{matrix_id}").status_code == 200
    assert matrix_id not in repr(captured)
    assert any(
        str(context.get("path", "")).endswith("/hpn/matrices/{matrix_id}")
        for context in captured
    )
