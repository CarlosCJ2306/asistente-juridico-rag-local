from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.models.document import KnowledgeLayer
from app.database.models.document_processing_job import (
    DocumentProcessingJob,
    DocumentProcessingState,
)
from app.database.repositories.document_processing_job_repository import (
    DocumentProcessingJobRepository,
)
from app.services import document_automation_service as automation_module
from app.services import embedding_runtime_service as runtime_module
from app.services.document_automation_service import (
    DocumentAutomationError,
    DocumentAutomationService,
    get_document_automation_service,
)
from app.services.embedding_runtime_service import EmbeddingRuntimeService
from app.database.session import get_db_session
from app.main import app


class FakeEmbeddingModel:
    def __init__(self) -> None:
        self.is_loaded = False
        self.load_calls = 0
        self.unload_calls = 0
        self.model_id = "synthetic-embedding"

    def load(self) -> None:
        self.load_calls += 1
        self.is_loaded = True

    def unload(self) -> None:
        self.unload_calls += 1
        self.is_loaded = False


async def _database(tmp_path: Path) -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'queue.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _configure_inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    inbox = tmp_path / "storage" / "inbox"
    monkeypatch.setattr(automation_module.settings, "document_inbox_private_path", inbox / "private_library")
    monkeypatch.setattr(automation_module.settings, "document_inbox_temporary_path", inbox / "temporary")
    monkeypatch.setattr(automation_module.settings, "document_inbox_processed_path", inbox / "processed")
    monkeypatch.setattr(automation_module.settings, "document_inbox_quarantine_path", inbox / "quarantine")
    monkeypatch.setattr(automation_module.settings, "document_inbox_stability_seconds", 0.01)
    return inbox


def test_scanner_requires_stable_pdf_and_enqueues_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        engine, factory = await _database(tmp_path)
        inbox = _configure_inbox(tmp_path, monkeypatch)
        service = DocumentAutomationService(factory, embedding_runtime=EmbeddingRuntimeService(FakeEmbeddingModel()))  # type: ignore[arg-type]
        service._ensure_roots()
        source = inbox / "private_library" / "sintetico.pdf"
        source.write_bytes(b"%PDF-1.7\nsynthetic")
        try:
            await service.scan_once()
            async with factory() as session:
                assert await DocumentProcessingJobRepository(session).next_queued() is None
            await asyncio.sleep(0.02)
            await service.scan_once()
            await service.scan_once()
            async with factory() as session:
                jobs = await DocumentProcessingJobRepository(session).recent(limit=10)
                assert len(jobs) == 1
                assert jobs[0].knowledge_layer is KnowledgeLayer.PRIVATE_LIBRARY
                assert jobs[0].state is DocumentProcessingState.QUEUED
        finally:
            await engine.dispose()  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_sidecars_are_strict_and_temporary_requires_future_expiration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox = _configure_inbox(tmp_path, monkeypatch)
    service = DocumentAutomationService.__new__(DocumentAutomationService)
    private = inbox / "private_library" / "private.pdf"
    private.parent.mkdir(parents=True)
    private.write_bytes(b"%PDF")
    assert service._read_sidecar(private, KnowledgeLayer.PRIVATE_LIBRARY).document_type.value == "otro"
    private.with_suffix(".json").write_text(
        json.dumps({"display_name": "Seguro", "stored_filename": "forbidden.pdf"}),
        encoding="utf-8",
    )
    with pytest.raises(DocumentAutomationError, match="DOCUMENT_SIDECAR_INVALID"):
        service._read_sidecar(private, KnowledgeLayer.PRIVATE_LIBRARY)

    temporary = inbox / "temporary" / "temporary.pdf"
    temporary.parent.mkdir(parents=True)
    temporary.write_bytes(b"%PDF")
    with pytest.raises(DocumentAutomationError, match="DOCUMENT_TEMPORARY_SIDECAR_REQUIRED"):
        service._read_sidecar(temporary, KnowledgeLayer.TEMPORARY)
    temporary.with_suffix(".json").write_text(
        json.dumps(
            {
                "display_name": "Temporal",
                "document_type": "normativa",
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    metadata = service._read_sidecar(temporary, KnowledgeLayer.TEMPORARY)
    assert metadata.document_type.value == "normativa"

    monkeypatch.setattr(automation_module.settings, "document_sidecar_max_bytes", 8)
    with pytest.raises(DocumentAutomationError, match="DOCUMENT_SIDECAR_INVALID"):
        service._read_sidecar(temporary, KnowledgeLayer.TEMPORARY)


def test_scanner_quarantines_a_file_that_never_stabilizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        engine, factory = await _database(tmp_path)
        inbox = _configure_inbox(tmp_path, monkeypatch)
        monkeypatch.setattr(
            automation_module.settings,
            "document_inbox_unstable_timeout_seconds",
            0.01,
        )
        service = DocumentAutomationService(
            factory,
            embedding_runtime=EmbeddingRuntimeService(FakeEmbeddingModel()),  # type: ignore[arg-type]
        )
        service._ensure_roots()
        source = inbox / "private_library" / "inestable.pdf"
        source.write_bytes(b"%PDF-1.7\nfirst")
        try:
            await service.scan_once()
            await asyncio.sleep(0.02)
            source.write_bytes(b"%PDF-1.7\nchanged")
            await service.scan_once()
            assert not source.exists()
            assert len(list((inbox / "quarantine").glob("*_inestable.pdf"))) == 1
        finally:
            await engine.dispose()  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_queue_recovers_incomplete_and_controls_retries(tmp_path: Path) -> None:
    async def scenario() -> None:
        engine, factory = await _database(tmp_path)
        try:
            async with factory() as session:
                job = DocumentProcessingJob(
                    knowledge_layer=KnowledgeLayer.PRIVATE_LIBRARY,
                    public_name="Sintético",
                    operation="upload_pipeline",
                    state=DocumentProcessingState.EXTRACTING,
                    attempts=1,
                )
                session.add(job)
                await session.commit()
                repository = DocumentProcessingJobRepository(session)
                assert await repository.recover_incomplete() == 1
                assert job.state is DocumentProcessingState.QUEUED
                await repository.transition(
                    job, DocumentProcessingState.FAILED, error_code="SAFE_ERROR"
                )
                assert await repository.retry(job, max_attempts=3)
                assert job.state is DocumentProcessingState.QUEUED
        finally:
            await engine.dispose()  # type: ignore[attr-defined]

    asyncio.run(scenario())


def test_embedding_runtime_loads_once_and_unloads_after_real_inactivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        model = FakeEmbeddingModel()
        runtime = EmbeddingRuntimeService(model)  # type: ignore[arg-type]
        monkeypatch.setattr(runtime_module.settings, "embedding_runtime_policy", "on_demand")
        monkeypatch.setattr(runtime_module.settings, "embedding_idle_unload_seconds", 0.01)

        async def operation() -> None:
            async with runtime.activity():
                await asyncio.sleep(0.01)

        await asyncio.gather(operation(), operation())
        assert model.load_calls == 1
        assert model.is_loaded
        await asyncio.sleep(0.03)
        assert model.unload_calls == 1
        assert not model.is_loaded

    asyncio.run(scenario())


def test_automation_singleton_does_not_retain_a_disposed_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_factory = object()
    second_factory = object()
    monkeypatch.setattr(automation_module, "_document_automation_service", None)

    first = get_document_automation_service(first_factory)  # type: ignore[arg-type]
    repeated = get_document_automation_service(first_factory)  # type: ignore[arg-type]
    replacement = get_document_automation_service(second_factory)  # type: ignore[arg-type]

    assert repeated is first
    assert replacement is not first
    assert replacement.session_factory is second_factory


def test_processing_api_returns_only_safe_queue_metadata(tmp_path: Path) -> None:
    async def prepare():
        engine, factory = await _database(tmp_path)
        async with factory() as session:
            session.add(
                DocumentProcessingJob(
                    knowledge_layer=KnowledgeLayer.PRIVATE_LIBRARY,
                    public_name="Documento sintético",
                    operation="inbox_import",
                    state=DocumentProcessingState.FAILED,
                    attempts=1,
                    error_code="SAFE_ERROR",
                    inbox_relative_path="private_library/private.pdf",
                )
            )
            await session.commit()
        return engine, factory

    engine, factory = asyncio.run(prepare())

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            summary = client.get("/api/documents/processing/summary")
            jobs = client.get("/api/documents/processing/jobs")
        assert summary.status_code == 200
        assert summary.json()["failed"] == 1
        assert jobs.status_code == 200
        serialized = jobs.text.lower()
        assert "inbox_relative_path" not in serialized
        assert "private_library/private.pdf" not in serialized
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(engine.dispose())
