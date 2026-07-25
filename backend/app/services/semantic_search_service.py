"""Búsqueda vectorial local validada finalmente contra SQLite."""

from __future__ import annotations

import asyncio
import html
import math
import time
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.repositories.semantic_chunk_repository import ActiveChunk
from app.schemas.semantic_search import (
    SemanticSearchItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.semantic_index_service import SemanticIndexService, SemanticServiceError
from app.vector_store.chroma_store import ChromaStoreError, VectorCandidate


@dataclass(frozen=True)
class _ValidatedCandidate:
    chunk: ActiveChunk
    distance: float


class SemanticSearchService:
    def __init__(self, index_service: SemanticIndexService) -> None:
        self.index_service = index_service

    async def search(
        self,
        request: SemanticSearchRequest,
        *,
        request_id: str | None = None,
    ) -> SemanticSearchResponse:
        normalized = self._normalize_query(request.query)
        state = await self.index_service.active_state(require_model=True)
        started_at = time.perf_counter()
        candidate_limit = min(
            request.top_k * settings.semantic_search_candidate_multiplier,
            settings.semantic_search_top_k_max
            * settings.semantic_search_candidate_multiplier,
        )
        log_info(
            "Iniciando búsqueda semántica local",
            operation="semantic_search",
            request_id=request_id,
            query_length=len(normalized),
            top_k=request.top_k,
            candidate_count=candidate_limit,
            filter_count=self._filter_count(request),
        )
        try:
            if state.indexed_chunks == 0:
                candidates: list[VectorCandidate] = []
                validated: list[_ValidatedCandidate] = []
                stale_count = 0
            else:
                query_vector = await asyncio.to_thread(
                    self.index_service.embedding_service.embed_query, normalized
                )
                if (
                    len(query_vector) != state.embedding_dimension
                    or not all(math.isfinite(value) for value in query_vector)
                ):
                    raise SemanticServiceError("SEMANTIC_OUTPUT_INVALID")
                candidates = await asyncio.to_thread(
                    self.index_service.store.query,
                    state.active_collection,
                    query_embedding=query_vector,
                    limit=candidate_limit,
                    where=self._chroma_filter(request),
                )
                validated, stale_count = await self._validate_candidates(
                    candidates, request
                )
        except SemanticServiceError:
            raise
        except ChromaStoreError as exc:
            log_error(
                "Búsqueda semántica no disponible",
                operation="semantic_search",
                request_id=request_id,
                query_length=len(normalized),
                top_k=request.top_k,
                error_code=exc.code,
            )
            raise SemanticServiceError(exc.code) from exc
        except Exception as exc:
            log_error(
                "Falló la búsqueda semántica",
                operation="semantic_search",
                request_id=request_id,
                query_length=len(normalized),
                top_k=request.top_k,
                error_code="SEMANTIC_SEARCH_ERROR",
            )
            raise SemanticServiceError("SEMANTIC_SEARCH_ERROR") from exc

        ordered = sorted(
            validated,
            key=lambda item: (
                item.distance,
                str(item.chunk.document_id),
                item.chunk.chunk_index,
                str(item.chunk.chunk_id),
            ),
        )[: request.top_k]
        response = SemanticSearchResponse(
            items=[
                SemanticSearchItem(
                    chunk_id=item.chunk.chunk_id,
                    document_id=item.chunk.document_id,
                    document_type=item.chunk.document_type,
                    chunk_index=item.chunk.chunk_index,
                    start_page=item.chunk.start_page,
                    end_page=item.chunk.end_page,
                    snippet=self._snippet(item.chunk.text),
                    distance_cosine=item.distance,
                )
                for item in ordered
            ],
            returned=len(ordered),
            top_k=request.top_k,
        )
        log_success(
            "Búsqueda semántica local completada",
            operation="semantic_search",
            request_id=request_id,
            query_length=len(normalized),
            top_k=request.top_k,
            candidate_count=len(candidates),
            returned=len(ordered),
            stale_discarded=stale_count,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return response

    async def _validate_candidates(
        self,
        candidates: list[VectorCandidate],
        request: SemanticSearchRequest,
    ) -> tuple[list[_ValidatedCandidate], int]:
        parsed: list[tuple[UUID, VectorCandidate]] = []
        seen: set[UUID] = set()
        for candidate in candidates:
            if not math.isfinite(candidate.distance):
                raise SemanticServiceError("SEMANTIC_OUTPUT_INVALID")
            try:
                chunk_id = UUID(candidate.chunk_id)
            except ValueError as exc:
                raise SemanticServiceError("SEMANTIC_OUTPUT_INVALID") from exc
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            parsed.append((chunk_id, candidate))
        active = await self.index_service.repository.get_active_by_ids(
            [chunk_id for chunk_id, _ in parsed]
        )
        validated: list[_ValidatedCandidate] = []
        stale = 0
        for chunk_id, candidate in parsed:
            chunk = active.get(chunk_id)
            if (
                chunk is None
                or not self._metadata_matches(candidate.metadata, chunk)
                or not self._filters_match(request, chunk)
            ):
                stale += 1
                continue
            validated.append(_ValidatedCandidate(chunk=chunk, distance=candidate.distance))
        return validated, stale

    @staticmethod
    def _normalize_query(query: str) -> str:
        normalized = unicodedata.normalize("NFC", query)
        if any(unicodedata.category(character).startswith("C") for character in normalized):
            raise SemanticServiceError("SEMANTIC_QUERY_INVALID")
        normalized = " ".join(normalized.split())
        if not normalized:
            raise SemanticServiceError("SEMANTIC_QUERY_EMPTY")
        if len(normalized) > settings.semantic_query_max_chars:
            raise SemanticServiceError("SEMANTIC_QUERY_TOO_LONG")
        return normalized

    @staticmethod
    def _metadata_matches(metadata: dict[str, object], chunk: ActiveChunk) -> bool:
        document_id = metadata.get("document_id")
        document_type = metadata.get("document_type")
        chunk_index = metadata.get("chunk_index")
        start_page = metadata.get("start_page")
        end_page = metadata.get("end_page")
        return (
            isinstance(document_id, str)
            and document_id == str(chunk.document_id)
            and isinstance(document_type, str)
            and document_type == chunk.document_type.value
            and type(chunk_index) is int
            and chunk_index == chunk.chunk_index
            and type(start_page) is int
            and start_page == chunk.start_page
            and type(end_page) is int
            and end_page == chunk.end_page
        )

    @staticmethod
    def _filters_match(request: SemanticSearchRequest, chunk: ActiveChunk) -> bool:
        if request.document_id is not None and chunk.document_id != request.document_id:
            return False
        if request.document_types and chunk.document_type not in request.document_types:
            return False
        if request.min_page is not None and chunk.start_page < request.min_page:
            return False
        return not (request.max_page is not None and chunk.end_page > request.max_page)

    @staticmethod
    def _chroma_filter(request: SemanticSearchRequest) -> dict[str, object] | None:
        clauses: list[dict[str, object]] = []
        if request.document_id is not None:
            clauses.append({"document_id": str(request.document_id)})
        if request.document_types:
            clauses.append(
                {"document_type": {"$in": [item.value for item in request.document_types]}}
            )
        if request.min_page is not None:
            clauses.append({"start_page": {"$gte": request.min_page}})
        if request.max_page is not None:
            clauses.append({"end_page": {"$lte": request.max_page}})
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    @staticmethod
    def _snippet(text: str) -> str:
        normalized = " ".join(text.split())
        escaped = html.escape(normalized, quote=False)
        limit = settings.semantic_snippet_max_length
        if len(escaped) <= limit:
            return escaped
        return f"{escaped[: limit - 1]}…"

    @staticmethod
    def _filter_count(request: SemanticSearchRequest) -> int:
        return sum(
            value is not None
            for value in (
                request.document_id,
                request.document_types,
                request.min_page,
                request.max_page,
            )
        )
