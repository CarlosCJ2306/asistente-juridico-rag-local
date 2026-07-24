"""Pruebas aisladas del bloque 2B: carga segura y API documental."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as document_routes
from app.database.base import Base
from app.database.session import DatabaseSessionManager, get_db_session
from app.main import app
from app.services.document_service import DocumentService


PDF_CONTENT = b"%PDF-1.7\ncontenido de prueba\n"


@pytest.fixture
def document_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Expone la API con SQLite y almacenamiento exclusivamente temporales."""

    project_root = tmp_path
    database_file = project_root / "storage" / "database" / "documents.db"
    database_file.parent.mkdir(parents=True)
    manager = DatabaseSessionManager(database_file)

    async def create_schema() -> None:
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    temporary_directory = project_root / "storage" / "temp" / "uploads"
    documents_directory = project_root / "storage" / "documents"

    def service_factory(session):
        return DocumentService(
            session,
            temporary_directory=temporary_directory,
            documents_directory=documents_directory,
            project_root=project_root,
            maximum_size_bytes=1024,
            chunk_size_bytes=8,
        )

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(document_routes, "_service", service_factory)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, project_root
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def _upload(client: TestClient, content: bytes = PDF_CONTENT, **overrides):
    filename = overrides.get("filename", "sentencia.pdf")
    content_type = overrides.get("content_type", "application/pdf")
    document_type = overrides.get("document_type", "expediente")
    return client.post(
        "/api/documents",
        data={"document_type": document_type},
        files={"file": (filename, content, content_type)},
    )


def test_upload_registers_pdf_in_category_and_returns_safe_metadata(document_client) -> None:
    client, project_root = document_client

    response = _upload(client, filename="../carpeta\\sentencia.pdf")

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "sentencia.pdf"
    assert body["status"] == "pending_extraction"
    assert body["relative_path"].startswith("storage/documents/expedientes/")
    assert body["sha256"] == hashlib.sha256(PDF_CONTENT).hexdigest()
    assert not Path(body["relative_path"]).is_absolute()
    assert (project_root / body["relative_path"]).read_bytes() == PDF_CONTENT
    assert not list((project_root / "storage" / "temp" / "uploads").glob("*.part"))


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("sentencia.txt", PDF_CONTENT, "application/pdf"),
        ("sentencia.pdf", PDF_CONTENT, "application/octet-stream"),
        ("sentencia.pdf", b"texto plano", "application/pdf"),
        ("sentencia.pdf", b"", "application/pdf"),
    ],
)
def test_upload_rejects_invalid_pdf_inputs(document_client, filename, content, content_type) -> None:
    client, project_root = document_client

    response = _upload(client, content, filename=filename, content_type=content_type)

    assert response.status_code == 400
    assert not list((project_root / "storage").rglob("*.pdf"))


def test_upload_rejects_oversized_content_and_cleans_temporary_file(document_client) -> None:
    client, project_root = document_client

    response = _upload(client, b"%PDF-" + b"a" * 1024)

    assert response.status_code == 413
    assert not list((project_root / "storage" / "temp").rglob("*.part"))
    assert not list((project_root / "storage").rglob("*.pdf"))


def test_duplicate_is_rejected_even_after_logical_deletion(document_client) -> None:
    client, project_root = document_client
    created = _upload(client)
    body = created.json()
    physical_path = project_root / body["relative_path"]

    duplicate = _upload(client)
    assert duplicate.status_code == 409
    duplicate_body = duplicate.json()
    assert duplicate_body["detail"] == "El documento ya está registrado"
    assert duplicate_body["existing_document_id"] == body["id"]
    assert client.get("/api/documents").json()["total"] == 1
    assert len(list((project_root / "storage" / "documents").rglob("*.pdf"))) == 1
    assert not list((project_root / "storage" / "temp" / "uploads").glob("*.part"))
    assert client.delete(f"/api/documents/{body['id']}").status_code == 204
    assert physical_path.exists()
    assert _upload(client).status_code == 409


def test_list_get_filters_pagination_and_logical_delete(document_client) -> None:
    client, _ = document_client
    first = _upload(client, b"%PDF-1.7\nuno", document_type="expediente").json()
    second = _upload(client, b"%PDF-1.7\ndos", document_type="normativa").json()

    listed = client.get("/api/documents", params={"document_type": "normativa"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == second["id"]
    assert client.get(f"/api/documents/{first['id']}").status_code == 200
    assert client.delete(f"/api/documents/{first['id']}").status_code == 204
    assert client.get(f"/api/documents/{first['id']}").status_code == 404
    assert client.get("/api/documents", params={"page": 1, "page_size": 1}).json()["total"] == 1


def test_document_routes_do_not_load_local_model(document_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = document_client

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("El modelo local no debe cargarse en rutas documentales")

    monkeypatch.setattr("app.ai.local_llm.LocalLLM.load", fail_if_called)
    assert client.get("/api/health").status_code == 200
    assert _upload(client).status_code == 201
