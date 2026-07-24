"""Pruebas aisladas de persistencia documental con SQLite temporal."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.paths import resolve_database_file
from app.database.base import Base
from app.database.models.document import DocumentStatus, DocumentType
from app.database.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.database.session import DatabaseSessionManager, database_session_manager
from app.main import app
from app.schemas.document import (
    DocumentCreate,
    DocumentListFilters,
    DocumentRead,
)


def document_data(
    suffix: str,
    *,
    document_type: DocumentType = DocumentType.EXPEDIENTE,
    status: DocumentStatus = DocumentStatus.REGISTERED,
) -> DocumentCreate:
    """Construye metadatos sintéticos sin crear ni leer archivos."""

    return DocumentCreate(
        original_filename=f"original-{suffix}.pdf",
        stored_filename=f"stored-{suffix}.pdf",
        relative_path=f"storage/documents/otros/{suffix}.pdf",
        document_type=document_type,
        mime_type="application/pdf",
        extension=".pdf",
        size_bytes=1024,
        sha256=hashlib.sha256(suffix.encode("utf-8")).hexdigest(),
        status=status,
    )


@pytest_asyncio.fixture
async def temporary_session(tmp_path: Path):
    """Crea tablas solo en una base temporal independiente."""

    database_file = tmp_path / "database" / "documents.db"
    database_file.parent.mkdir()
    manager = DatabaseSessionManager(database_file)
    assert database_file.exists() is False
    engine = manager.get_engine()
    assert database_file.exists() is False
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = manager.get_session_factory()
    async with session_factory() as session:
        yield session
    await manager.dispose()


def test_database_path_is_limited_to_project_database_directory() -> None:
    safe_settings = Settings(
        _env_file=None,
        database_file="storage/database/test_database.db",
    )

    assert safe_settings.database_file.name == "test_database.db"
    with pytest.raises(ValueError, match="storage/database"):
        resolve_database_file("../outside.db")
    with pytest.raises(ValidationError, match="storage/database"):
        Settings(_env_file=None, database_file="../outside.db")


def test_engine_creation_is_deferred_and_does_not_create_file(tmp_path: Path) -> None:
    database_file = tmp_path / "deferred.db"
    manager = DatabaseSessionManager(database_file)

    assert manager.is_initialized is False
    assert database_file.exists() is False
    manager.get_engine()
    assert manager.is_initialized is True
    assert database_file.exists() is False


def test_imported_session_manager_does_not_initialize_engine() -> None:
    assert database_session_manager.is_initialized is False


def test_fastapi_startup_does_not_initialize_database_engine() -> None:
    assert database_session_manager.is_initialized is False

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert database_session_manager.is_initialized is False


@pytest.mark.asyncio
async def test_create_and_find_document(temporary_session: AsyncSession) -> None:
    repository = DocumentRepository(temporary_session)
    created = await repository.create(document_data("a"))

    assert created.id is not None
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None
    assert await repository.get_by_id(created.id) == created
    assert await repository.get_by_sha256(created.sha256.upper()) == created


@pytest.mark.asyncio
async def test_duplicate_sha256_is_rejected_without_breaking_session(
    temporary_session: AsyncSession,
) -> None:
    repository = DocumentRepository(temporary_session)
    await repository.create(document_data("b"))

    duplicate = document_data("b")
    duplicate.relative_path = "documents/other-b.pdf"
    with pytest.raises(DuplicateDocumentError, match="sha256"):
        await repository.create(duplicate)

    assert await repository.count(DocumentListFilters()) == 1


@pytest.mark.asyncio
async def test_list_filters_pagination_and_soft_delete(
    temporary_session: AsyncSession,
) -> None:
    repository = DocumentRepository(temporary_session)
    expediente = await repository.create(document_data("c"))
    await repository.create(
        document_data(
            "d",
            document_type=DocumentType.NORMATIVA,
            status=DocumentStatus.STORED,
        )
    )
    await repository.create(
        document_data(
            "e",
            document_type=DocumentType.NORMATIVA,
            status=DocumentStatus.FAILED,
        )
    )

    normative_filter = DocumentListFilters(document_type=DocumentType.NORMATIVA)
    assert await repository.count(normative_filter) == 2
    assert len(await repository.list(DocumentListFilters(limit=1))) == 1
    failed = await repository.list(
        DocumentListFilters(status=DocumentStatus.FAILED)
    )
    assert len(failed) == 1
    assert failed[0].document_type is DocumentType.NORMATIVA

    deleted = await repository.soft_delete(expediente.id)
    assert deleted is not None
    assert deleted.is_deleted is True
    assert deleted.status is DocumentStatus.ARCHIVED
    assert deleted.deleted_at is not None
    assert await repository.get_by_id(expediente.id) is None
    assert await repository.count(DocumentListFilters()) == 2
    assert await repository.count(DocumentListFilters(include_deleted=True)) == 3


def test_document_schema_rejects_unsafe_paths_and_long_filenames() -> None:
    unsafe_path_data = document_data("f").model_dump()
    unsafe_path_data["relative_path"] = "../sensitive.pdf"
    with pytest.raises(ValidationError, match="ruta relativa segura"):
        DocumentCreate(**unsafe_path_data)

    long_filename_data = document_data("g").model_dump()
    long_filename_data["original_filename"] = "x" * 256
    with pytest.raises(ValidationError, match="at most 255 characters"):
        DocumentCreate(**long_filename_data)


@pytest.mark.asyncio
async def test_safe_serialization_never_exposes_absolute_path(
    temporary_session: AsyncSession,
) -> None:
    repository = DocumentRepository(temporary_session)
    created = await repository.create(document_data("h"))
    serialized = DocumentRead.model_validate(created).model_dump(mode="json")

    assert serialized["relative_path"] == "storage/documents/otros/h.pdf"
    assert "error_message" not in serialized
    assert str(created.id) in serialized["id"]
