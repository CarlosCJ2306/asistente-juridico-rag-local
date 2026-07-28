"""Bandejas locales, cola persistente y pipeline documental automático."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers

from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    SourceKind,
)
from app.database.models.document_processing_job import (
    DocumentProcessingJob,
    DocumentProcessingState,
)
from app.database.repositories.document_processing_job_repository import (
    DocumentProcessingJobRepository,
)
from app.database.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.schemas.document import DocumentUploadGovernance
from app.services.document_extraction_service import (
    DocumentExtractionError,
    DocumentExtractionService,
)
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
)
from app.services.embedding_runtime_service import (
    EmbeddingRuntimeService,
    get_embedding_runtime_service,
)
from app.services.semantic_index_service import SemanticIndexService


_SAFE_NAME = re.compile(r"[^\w .()\-]+", flags=re.UNICODE)


class DocumentAutomationError(RuntimeError):
    def __init__(self, code: str, *, quarantine: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.quarantine = quarantine


class _PrivateSidecar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    document_type: DocumentType = DocumentType.OTRO

    @field_validator("display_name")
    @classmethod
    def safe_display_name(cls, value: str | None) -> str | None:
        return _normalize_public_name(value) if value is not None else None


class _TemporarySidecar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=255)
    document_type: DocumentType = DocumentType.OTRO
    expires_at: datetime

    @field_validator("display_name")
    @classmethod
    def safe_display_name(cls, value: str) -> str:
        return _normalize_public_name(value)

    @field_validator("expires_at")
    @classmethod
    def future_expiration(cls, value: datetime) -> datetime:
        if value.utcoffset() is None or value <= datetime.now(timezone.utc):
            raise ValueError("DOCUMENT_TEMPORARY_EXPIRATION_REQUIRED")
        return value


def _normalize_public_name(value: str | None) -> str:
    if value is None:
        raise ValueError("DOCUMENT_PUBLIC_NAME_INVALID")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 255 or any(ord(char) < 32 for char in normalized):
        raise ValueError("DOCUMENT_PUBLIC_NAME_INVALID")
    return normalized


def _sanitized_filename(value: str) -> str:
    normalized = _SAFE_NAME.sub("_", Path(value).name).strip(" ._")
    return (normalized or "documento.pdf")[:255]


class DocumentAutomationService:
    """Procesa una cola local mediante un único coordinador por proceso."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        embedding_runtime: EmbeddingRuntimeService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_runtime = embedding_runtime or get_embedding_runtime_service()
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._observed: dict[str, tuple[int, int, float, float]] = {}

    async def start(self) -> None:
        if not settings.document_automation_enabled or self._task is not None:
            return
        self._ensure_roots()
        async with self.session_factory() as session:
            repository = DocumentProcessingJobRepository(session)
            try:
                recovered = await repository.recover_incomplete()
                await session.commit()
            except Exception:
                await session.rollback()
                log_error(
                    "Cola automática no disponible",
                    operation="document_automation_start",
                    error_code="DOCUMENT_PROCESSING_QUEUE_NOT_READY",
                )
                return
        log_info(
            "Procesamiento documental automático iniciado",
            operation="document_automation_start",
            recovered_jobs=recovered,
        )
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def run_once(self) -> None:
        if self._run_lock.locked():
            return
        async with self._run_lock:
            await self.scan_once()
            while await self._process_next_job():
                pass
            await self._index_waiting_batch()

    async def scan_once(self) -> None:
        self._ensure_roots()
        now = time.monotonic()
        inspected = 0
        for layer, root in self._source_roots().items():
            for candidate in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
                if inspected >= settings.document_inbox_max_files_per_scan:
                    return
                inspected += 1
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                relative = candidate.relative_to(self._inbox_root()).as_posix()
                try:
                    stat = candidate.stat()
                except OSError:
                    continue
                previous = self._observed.get(relative)
                signature = (stat.st_size, stat.st_mtime_ns)
                if previous is None:
                    self._observed[relative] = (*signature, now, now)
                    continue
                if previous[:2] != signature:
                    if (
                        now - previous[3]
                        >= settings.document_inbox_unstable_timeout_seconds
                    ):
                        await self._quarantine_untracked(
                            candidate, "DOCUMENT_INBOX_UNSTABLE"
                        )
                        self._observed.pop(relative, None)
                        continue
                    self._observed[relative] = (*signature, now, previous[3])
                    continue
                if now - previous[2] < settings.document_inbox_stability_seconds:
                    continue
                suffix = candidate.suffix.lower()
                if suffix == ".json":
                    continue
                if suffix != ".pdf":
                    await self._quarantine_untracked(candidate, "DOCUMENT_INBOX_EXTENSION_INVALID")
                    self._observed.pop(relative, None)
                    continue
                async with self.session_factory() as session:
                    repository = DocumentProcessingJobRepository(session)
                    try:
                        await repository.create_inbox_job(
                            knowledge_layer=layer,
                            public_name=_sanitized_filename(candidate.stem),
                            inbox_relative_path=relative,
                        )
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        log_error(
                            "No fue posible registrar un archivo detectado",
                            operation="document_inbox_scan",
                            error_code="DOCUMENT_PROCESSING_QUEUE_ERROR",
                        )
                self._observed.pop(relative, None)

    async def enqueue_uploaded_document(
        self,
        *,
        document_id: UUID,
        knowledge_layer: KnowledgeLayer,
        public_name: str,
    ) -> UUID:
        async with self.session_factory() as session:
            repository = DocumentProcessingJobRepository(session)
            job = await repository.create_upload_job(
                document_id=document_id,
                knowledge_layer=knowledge_layer,
                public_name=_normalize_public_name(public_name),
            )
            await session.commit()
            return job.id

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log_error(
                    "Falló un ciclo de automatización documental",
                    operation="document_automation_cycle",
                    error_code="DOCUMENT_AUTOMATION_ERROR",
                )
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=settings.document_inbox_scan_interval_seconds,
                )
            except TimeoutError:
                continue

    async def _process_next_job(self) -> bool:
        async with self.session_factory() as session:
            repository = DocumentProcessingJobRepository(session)
            job = await repository.next_queued()
            if job is None:
                return False
            await repository.transition(
                job,
                DocumentProcessingState.DETECTING,
                increment_attempts=True,
            )
            await session.commit()
            try:
                await self._register_if_needed(session, repository, job)
                if job.document_id is None:
                    raise DocumentAutomationError("DOCUMENT_REGISTRATION_FAILED")
                document = await DocumentExtractionService(session).documents.get_by_id(
                    job.document_id
                )
                if document is None:
                    raise DocumentAutomationError("DOCUMENT_NOT_FOUND")
                if document.status is not DocumentStatus.EXTRACTED:
                    await repository.transition(job, DocumentProcessingState.EXTRACTING)
                    await session.commit()
                    await DocumentExtractionService(session).extract(document.id)
                await repository.transition(
                    job, DocumentProcessingState.WAITING_FOR_INDEX
                )
                await session.commit()
                return True
            except DocumentAutomationError as exc:
                await self._finish_failure(session, repository, job, exc)
            except DocumentExtractionError as exc:
                await self._finish_failure(
                    session,
                    repository,
                    job,
                    DocumentAutomationError(exc.code),
                )
            except (DocumentServiceError, ValidationError):
                await self._finish_failure(
                    session,
                    repository,
                    job,
                    DocumentAutomationError(
                        "DOCUMENT_INBOX_INVALID", quarantine=True
                    ),
                )
            except Exception:
                await self._finish_failure(
                    session,
                    repository,
                    job,
                    DocumentAutomationError("DOCUMENT_PROCESSING_ERROR"),
                )
            return True

    async def _register_if_needed(
        self,
        session: AsyncSession,
        repository: DocumentProcessingJobRepository,
        job: DocumentProcessingJob,
    ) -> None:
        if job.document_id is not None:
            return
        source = self._resolve_job_source(job)
        metadata = self._read_sidecar(source, job.knowledge_layer)
        job.public_name = metadata.display_name or _sanitized_filename(source.stem)
        await repository.transition(job, DocumentProcessingState.REGISTERING)
        await session.commit()
        stream: BinaryIO = source.open("rb")
        upload = UploadFile(
            file=stream,
            filename=source.name,
            headers=Headers({"content-type": "application/pdf"}),
        )
        governance = DocumentUploadGovernance(
            display_name=job.public_name,
            knowledge_layer=job.knowledge_layer,
            source_kind=SourceKind.LOCAL_UPLOAD,
            expires_at=getattr(metadata, "expires_at", None),
        )
        try:
            created = await DocumentService(session).upload_pdf(
                upload, metadata.document_type, governance
            )
            document_id = created.id
        except DuplicateDocumentError as exc:
            if exc.existing_document_id is None:
                raise
            document_id = exc.existing_document_id
        await repository.transition(
            job,
            DocumentProcessingState.EXTRACTING,
            document_id=document_id,
        )
        await session.commit()

    async def _index_waiting_batch(self) -> None:
        async with self.session_factory() as session:
            repository = DocumentProcessingJobRepository(session)
            jobs = await repository.waiting_for_index()
            if not jobs:
                return
            for job in jobs:
                await repository.transition(job, DocumentProcessingState.INDEXING)
            await session.commit()
            try:
                if settings.document_index_debounce_seconds:
                    await asyncio.sleep(settings.document_index_debounce_seconds)
                async with self.embedding_runtime.activity():
                    await SemanticIndexService(session).rebuild()
                documents = DocumentRepository(session)
                for job in jobs:
                    document = (
                        await documents.get_by_id(job.document_id)
                        if job.document_id is not None
                        else None
                    )
                    if document is None or document.index_status is not IndexStatus.INDEXED:
                        await repository.transition(
                            job,
                            DocumentProcessingState.FAILED,
                            error_code="DOCUMENT_NOT_INDEXABLE",
                        )
                        continue
                    await repository.transition(
                        job, DocumentProcessingState.COMPLETED
                    )
                    await self._archive_inbox_source(job, processed=True)
                await session.commit()
                log_success(
                    "Lote documental procesado e indexado",
                    operation="document_automation_batch",
                    job_count=len(jobs),
                )
            except Exception as exc:
                code = getattr(exc, "code", "DOCUMENT_INDEXING_ERROR")
                await session.rollback()
                jobs = await repository.waiting_for_index()
                if not jobs:
                    rows = await repository.recent(limit=settings.document_processing_recent_limit)
                    jobs = [
                        job
                        for job in rows
                        if job.state is DocumentProcessingState.INDEXING
                    ]
                for job in jobs:
                    await repository.transition(
                        job,
                        DocumentProcessingState.FAILED,
                        error_code=code,
                    )
                await session.commit()
                log_error(
                    "No fue posible indexar el lote documental",
                    operation="document_automation_batch",
                    error_code=code,
                    job_count=len(jobs),
                )

    async def _finish_failure(
        self,
        session: AsyncSession,
        repository: DocumentProcessingJobRepository,
        job: DocumentProcessingJob,
        error: DocumentAutomationError,
    ) -> None:
        await session.rollback()
        refreshed = await repository.get(job.id)
        if refreshed is None:
            return
        quarantine = error.quarantine or refreshed.attempts >= settings.document_processing_max_retries
        state = (
            DocumentProcessingState.QUARANTINED
            if quarantine
            else DocumentProcessingState.FAILED
        )
        await repository.transition(refreshed, state, error_code=error.code)
        if quarantine:
            await self._archive_inbox_source(refreshed, processed=False)
        await session.commit()
        log_error(
            "Procesamiento documental no completado",
            operation="document_automation_job",
            error_code=error.code,
            state=state.value,
        )

    def _read_sidecar(
        self, source: Path, layer: KnowledgeLayer
    ) -> _PrivateSidecar | _TemporarySidecar:
        sidecar = source.with_suffix(".json")
        if not sidecar.exists():
            if layer is KnowledgeLayer.TEMPORARY:
                raise DocumentAutomationError(
                    "DOCUMENT_TEMPORARY_SIDECAR_REQUIRED", quarantine=True
                )
            return _PrivateSidecar()
        if (
            sidecar.is_symlink()
            or not sidecar.is_file()
            or sidecar.stat().st_size > settings.document_sidecar_max_bytes
        ):
            raise DocumentAutomationError("DOCUMENT_SIDECAR_INVALID", quarantine=True)
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            model = _TemporarySidecar if layer is KnowledgeLayer.TEMPORARY else _PrivateSidecar
            return model.model_validate(payload)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise DocumentAutomationError(
                "DOCUMENT_SIDECAR_INVALID", quarantine=True
            ) from exc

    def _resolve_job_source(self, job: DocumentProcessingJob) -> Path:
        if job.inbox_relative_path is None:
            raise DocumentAutomationError("DOCUMENT_INBOX_PATH_INVALID")
        relative = Path(job.inbox_relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise DocumentAutomationError("DOCUMENT_INBOX_PATH_INVALID", quarantine=True)
        source = (self._inbox_root() / relative).resolve()
        expected_root = self._source_roots().get(job.knowledge_layer)
        if expected_root is None or source.parent != expected_root.resolve():
            raise DocumentAutomationError("DOCUMENT_INBOX_PATH_INVALID", quarantine=True)
        if source.is_symlink() or not source.is_file() or source.suffix.lower() != ".pdf":
            raise DocumentAutomationError("DOCUMENT_INBOX_FILE_INVALID", quarantine=True)
        return source

    async def _archive_inbox_source(
        self, job: DocumentProcessingJob, *, processed: bool
    ) -> None:
        if job.inbox_relative_path is None:
            return
        try:
            source = self._resolve_job_source(job)
        except DocumentAutomationError:
            return
        target_root = (
            settings.document_inbox_processed_path
            if processed
            else settings.document_inbox_quarantine_path
        )
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / f"{uuid4().hex}_{_sanitized_filename(source.name)}"
        os.replace(source, target)
        sidecar = source.with_suffix(".json")
        if sidecar.is_file() and not sidecar.is_symlink():
            os.replace(sidecar, target.with_suffix(".json"))

    async def _quarantine_untracked(self, source: Path, code: str) -> None:
        target_root = settings.document_inbox_quarantine_path
        target_root.mkdir(parents=True, exist_ok=True)
        os.replace(
            source,
            target_root / f"{uuid4().hex}_{_sanitized_filename(source.name)}",
        )
        log_error(
            "Archivo de bandeja enviado a cuarentena",
            operation="document_inbox_quarantine",
            error_code=code,
        )

    @staticmethod
    def _source_roots() -> dict[KnowledgeLayer, Path]:
        return {
            KnowledgeLayer.PRIVATE_LIBRARY: settings.document_inbox_private_path,
            KnowledgeLayer.TEMPORARY: settings.document_inbox_temporary_path,
        }

    @staticmethod
    def _inbox_root() -> Path:
        private_parent = settings.document_inbox_private_path.parent.resolve()
        if settings.document_inbox_temporary_path.parent.resolve() != private_parent:
            raise DocumentAutomationError("DOCUMENT_INBOX_PATH_INVALID")
        return private_parent

    @staticmethod
    def _ensure_roots() -> None:
        for root in (
            settings.document_inbox_private_path,
            settings.document_inbox_temporary_path,
            settings.document_inbox_processed_path,
            settings.document_inbox_quarantine_path,
        ):
            if root.exists() and root.is_symlink():
                raise DocumentAutomationError("DOCUMENT_INBOX_PATH_INVALID")
            root.mkdir(parents=True, exist_ok=True)


_document_automation_service: DocumentAutomationService | None = None


def get_document_automation_service(
    session_factory: async_sessionmaker[AsyncSession],
) -> DocumentAutomationService:
    global _document_automation_service
    if _document_automation_service is None or (
        _document_automation_service.session_factory is not session_factory
        and _document_automation_service._task is None
    ):
        _document_automation_service = DocumentAutomationService(session_factory)
    return _document_automation_service
