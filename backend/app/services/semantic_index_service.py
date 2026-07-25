"""Coordinación segura del índice semántico derivado de SQLite."""

from __future__ import annotations

import asyncio
import hashlib
import math
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embedding_model import EMBEDDING_MODEL_ID, EmbeddingError, EmbeddingModel, get_embedding_model
from app.core.Log import log_error, log_info, log_success, log_warning
from app.core.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.repositories.semantic_chunk_repository import (
    ActiveChunk,
    SemanticChunkRepository,
    update_source_fingerprint,
)
from app.schemas.semantic_search import (
    SemanticIndexStatusName,
    SemanticRebuildResponse,
    SemanticStatusResponse,
)
from app.services.embedding_service import EmbeddingService
from app.vector_store.chroma_store import ChromaStore, ChromaStoreError
from app.vector_store.semantic_index_state import (
    SemanticIndexState,
    SemanticStateError,
    SemanticStateStore,
)


class SemanticServiceError(RuntimeError):
    """Error semántico estable y apto para la API."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SemanticIndexService:
    """Construye una colección temporal y activa solo índices validados."""

    _rebuild_lock = threading.Lock()
    _building = False
    _last_error_code: str | None = None

    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_model: EmbeddingModel | None = None,
        store: ChromaStore | None = None,
        state_store: SemanticStateStore | None = None,
    ) -> None:
        self.repository = SemanticChunkRepository(session)
        self.embedding_model = embedding_model or get_embedding_model()
        self.embedding_service = EmbeddingService(self.embedding_model)
        self.store = store or ChromaStore()
        self.state_store = state_store or SemanticStateStore()

    async def status(self) -> SemanticStatusResponse:
        snapshot = await self.repository.source_snapshot(
            batch_size=settings.semantic_index_batch_size
        )
        active_chunks = snapshot.chunk_count
        dependency_available = self.store.dependency_available()
        try:
            state = await asyncio.to_thread(self.state_store.read)
        except SemanticStateError as exc:
            return SemanticStatusResponse(
                state="error",
                dependency_available=dependency_available,
                embedding_model=EMBEDDING_MODEL_ID,
                embedding_dimension=self.embedding_model.dimension,
                indexed_chunks=0,
                active_chunks=active_chunks,
                needs_rebuild=True,
                error_code=exc.code,
            )
        if state is None:
            if (
                dependency_available
                and type(self)._last_error_code is not None
                and not type(self)._building
            ):
                return SemanticStatusResponse(
                    state="error",
                    dependency_available=dependency_available,
                    embedding_model=EMBEDDING_MODEL_ID,
                    embedding_dimension=self.embedding_model.dimension,
                    indexed_chunks=0,
                    active_chunks=active_chunks,
                    needs_rebuild=True,
                    error_code=type(self)._last_error_code,
                )
            return SemanticStatusResponse(
                state="building" if type(self)._building else (
                    "not_ready" if dependency_available else "unavailable"
                ),
                dependency_available=dependency_available,
                embedding_model=EMBEDDING_MODEL_ID,
                embedding_dimension=self.embedding_model.dimension,
                indexed_chunks=0,
                active_chunks=active_chunks,
                needs_rebuild=True,
                error_code=None if dependency_available else "CHROMA_DEPENDENCY_MISSING",
            )
        error_code: str | None = None
        state_name: SemanticIndexStatusName = (
            "building" if type(self)._building else "ready"
        )
        if type(self)._last_error_code is not None and not type(self)._building:
            state_name = "error"
            error_code = type(self)._last_error_code
        try:
            self._validate_state(state, model_dimension=None)
            if dependency_available:
                await self._validate_collection(state)
            else:
                state_name = "unavailable"
                error_code = "CHROMA_DEPENDENCY_MISSING"
        except SemanticServiceError as exc:
            state_name = "error"
            error_code = exc.code
        return SemanticStatusResponse(
            state=state_name,
            dependency_available=dependency_available,
            embedding_model=EMBEDDING_MODEL_ID,
            embedding_dimension=state.embedding_dimension,
            indexed_chunks=state.indexed_chunks,
            active_chunks=active_chunks,
            needs_rebuild=(
                state.source_fingerprint != snapshot.fingerprint
                or state.indexed_chunks != active_chunks
                or state_name != "ready"
            ),
            error_code=error_code,
        )

    async def rebuild(self, *, request_id: str | None = None) -> SemanticRebuildResponse:
        if not self.store.dependency_available():
            raise SemanticServiceError("CHROMA_DEPENDENCY_MISSING")
        dimension = self.embedding_model.dimension
        if (
            not self.embedding_model.is_loaded
            or isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension <= 0
        ):
            raise SemanticServiceError("EMBEDDING_MODEL_NOT_LOADED")
        if not type(self)._rebuild_lock.acquire(blocking=False):
            raise SemanticServiceError("SEMANTIC_INDEX_BUSY")

        type(self)._building = True
        type(self)._last_error_code = None
        started_at = time.perf_counter()
        temporary_name = ""
        temporary_cleanup_required = False
        old_state: SemanticIndexState | None = None
        indexed = 0
        indexed_digest = hashlib.sha256()
        seen_chunk_ids: set[str] = set()
        try:
            try:
                old_state = await asyncio.to_thread(self.state_store.read)
            except SemanticStateError as exc:
                raise SemanticServiceError(exc.code) from exc
            temporary_name = self._new_collection_name(old_state)
            log_info(
                "Iniciando reconstrucción del índice semántico",
                operation="semantic_index_rebuild",
                request_id=request_id,
                embedding_model=EMBEDDING_MODEL_ID,
                embedding_dimension=dimension,
                batch_size=settings.semantic_index_batch_size,
            )
            temporary_cleanup_required = True
            await asyncio.to_thread(
                self.store.create_collection,
                temporary_name,
                schema_version=settings.semantic_index_schema_version,
                embedding_model=settings.embedding_model_name,
                embedding_dimension=dimension,
            )
            offset = 0
            while True:
                chunks = await self.repository.list_active_batch(
                    offset=offset, limit=settings.semantic_index_batch_size
                )
                if not chunks:
                    break
                embedded = await asyncio.to_thread(
                    self.embedding_service.embed_chunks,
                    [self._as_document_chunk(chunk) for chunk in chunks],
                )
                vectors = [item.vector for item in embedded]
                self._validate_vectors(
                    vectors, dimension, expected_count=len(chunks)
                )
                chunk_ids = [str(chunk.chunk_id) for chunk in chunks]
                if any(chunk_id in seen_chunk_ids for chunk_id in chunk_ids):
                    raise SemanticServiceError("SEMANTIC_OUTPUT_INVALID")
                seen_chunk_ids.update(chunk_ids)
                for chunk in chunks:
                    update_source_fingerprint(indexed_digest, chunk)
                await asyncio.to_thread(
                    self.store.add,
                    temporary_name,
                    ids=chunk_ids,
                    embeddings=vectors,
                    metadatas=[self._metadata(chunk) for chunk in chunks],
                )
                indexed += len(chunks)
                offset += len(chunks)

            source_snapshot = await self.repository.source_snapshot(
                batch_size=settings.semantic_index_batch_size
            )
            source_count = source_snapshot.chunk_count
            stored_count = await asyncio.to_thread(self.store.count, temporary_name)
            if (
                indexed != source_count
                or stored_count != source_count
                or indexed_digest.hexdigest() != source_snapshot.fingerprint
            ):
                raise SemanticServiceError("SEMANTIC_INDEX_BUILD_ERROR")
            collection_metadata = await asyncio.to_thread(
                self.store.metadata, temporary_name
            )
            self._validate_collection_metadata(collection_metadata, dimension)
            new_state = SemanticIndexState(
                schema_version=settings.semantic_index_schema_version,
                active_collection=temporary_name,
                embedding_model=settings.embedding_model_name,
                embedding_dimension=dimension,
                distance_metric="cosine",
                indexed_chunks=indexed,
                created_at=datetime.now(timezone.utc).isoformat(),
                source_fingerprint=source_snapshot.fingerprint,
            )
            await asyncio.to_thread(self.state_store.write_atomic, new_state)
            temporary_cleanup_required = False
            if old_state is not None and old_state.active_collection != temporary_name:
                try:
                    await asyncio.to_thread(
                        self.store.delete_collection, old_state.active_collection
                    )
                except ChromaStoreError:
                    log_warning(
                        "No fue posible retirar la colección semántica anterior",
                        operation="semantic_index_cleanup",
                        error_code="SEMANTIC_INDEX_CLEANUP_ERROR",
                    )
            log_success(
                "Índice semántico reconstruido",
                operation="semantic_index_rebuild",
                request_id=request_id,
                indexed_chunks=indexed,
                embedding_dimension=dimension,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            type(self)._last_error_code = None
            return SemanticRebuildResponse(
                indexed_chunks=indexed,
                embedding_dimension=dimension,
            )
        except SemanticServiceError as exc:
            self._log_rebuild_error(exc.code, request_id, started_at)
            raise
        except EmbeddingError as exc:
            code = exc.code if exc.code == "EMBEDDING_MODEL_NOT_LOADED" else "SEMANTIC_INDEX_BUILD_ERROR"
            self._log_rebuild_error(code, request_id, started_at)
            raise SemanticServiceError(code) from exc
        except (ChromaStoreError, SemanticStateError) as exc:
            code = getattr(exc, "code", "SEMANTIC_INDEX_BUILD_ERROR")
            self._log_rebuild_error(code, request_id, started_at)
            raise SemanticServiceError(code) from exc
        except Exception as exc:
            self._log_rebuild_error("SEMANTIC_INDEX_BUILD_ERROR", request_id, started_at)
            raise SemanticServiceError("SEMANTIC_INDEX_BUILD_ERROR") from exc
        finally:
            if temporary_cleanup_required and temporary_name:
                try:
                    await asyncio.to_thread(self.store.delete_collection, temporary_name)
                except ChromaStoreError:
                    log_warning(
                        "No fue posible retirar una colección temporal fallida",
                        operation="semantic_index_cleanup",
                        error_code="SEMANTIC_INDEX_TEMP_CLEANUP_ERROR",
                    )
            type(self)._building = False
            type(self)._rebuild_lock.release()

    async def active_state(self, *, require_model: bool) -> SemanticIndexState:
        if not self.store.dependency_available():
            raise SemanticServiceError("CHROMA_DEPENDENCY_MISSING")
        if require_model and (
            not self.embedding_model.is_loaded or self.embedding_model.dimension is None
        ):
            raise SemanticServiceError("EMBEDDING_MODEL_NOT_LOADED")
        try:
            state = await asyncio.to_thread(self.state_store.read)
        except SemanticStateError as exc:
            raise SemanticServiceError(exc.code) from exc
        if state is None:
            raise SemanticServiceError("SEMANTIC_INDEX_NOT_READY")
        self._validate_state(
            state,
            model_dimension=self.embedding_model.dimension if require_model else None,
        )
        await self._validate_collection(state)
        return state

    async def _validate_collection(self, state: SemanticIndexState) -> None:
        try:
            count = await asyncio.to_thread(self.store.count, state.active_collection)
            metadata = await asyncio.to_thread(self.store.metadata, state.active_collection)
        except ChromaStoreError as exc:
            raise SemanticServiceError(exc.code) from exc
        if count != state.indexed_chunks:
            raise SemanticServiceError("SEMANTIC_INDEX_INCOMPATIBLE")
        self._validate_collection_metadata(metadata, state.embedding_dimension)

    @staticmethod
    def _validate_state(
        state: SemanticIndexState, *, model_dimension: int | None
    ) -> None:
        if (
            state.schema_version != settings.semantic_index_schema_version
            or state.embedding_model != settings.embedding_model_name
            or state.distance_metric != "cosine"
            or (model_dimension is not None and state.embedding_dimension != model_dimension)
        ):
            raise SemanticServiceError("SEMANTIC_INDEX_INCOMPATIBLE")

    @staticmethod
    def _validate_collection_metadata(metadata: dict[str, object], dimension: int) -> None:
        if (
            metadata.get("hnsw:space") != "cosine"
            or metadata.get("semantic_schema_version") != settings.semantic_index_schema_version
            or metadata.get("embedding_model") != settings.embedding_model_name
            or metadata.get("embedding_dimension") != dimension
        ):
            raise SemanticServiceError("SEMANTIC_INDEX_INCOMPATIBLE")

    @staticmethod
    def _validate_vectors(
        vectors: list[list[float]], dimension: int, *, expected_count: int
    ) -> None:
        if len(vectors) != expected_count or any(
            len(vector) != dimension or not all(math.isfinite(value) for value in vector)
            for vector in vectors
        ):
            raise SemanticServiceError("SEMANTIC_OUTPUT_INVALID")

    @staticmethod
    def _new_collection_name(old_state: SemanticIndexState | None) -> str:
        while True:
            name = f"{settings.semantic_collection_prefix}_{uuid4().hex}"
            if old_state is None or name != old_state.active_collection:
                return name

    @staticmethod
    def _metadata(chunk: ActiveChunk) -> dict[str, str | int]:
        return {
            "document_id": str(chunk.document_id),
            "document_type": chunk.document_type.value,
            "chunk_index": chunk.chunk_index,
            "start_page": chunk.start_page,
            "end_page": chunk.end_page,
        }

    @staticmethod
    def _as_document_chunk(chunk: ActiveChunk) -> DocumentChunk:
        return DocumentChunk(
            id=chunk.chunk_id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            char_count=len(chunk.text),
            word_count=len(chunk.text.split()),
            start_page=chunk.start_page,
            end_page=chunk.end_page,
        )

    @staticmethod
    def _log_rebuild_error(
        code: str, request_id: str | None, started_at: float
    ) -> None:
        SemanticIndexService._last_error_code = code
        log_error(
            "Falló la reconstrucción del índice semántico",
            operation="semantic_index_rebuild",
            request_id=request_id,
            error_code=code,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
