"""Fusión determinista de resultados FTS5 y ChromaDB mediante RRF."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.embedding_model import EmbeddingError

from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.repositories.semantic_chunk_repository import (
    ActiveChunk,
    SemanticChunkRepository,
)
from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.schemas.hybrid_search import (
    HybridSearchItem,
    HybridSearchRequest,
    HybridSearchResponse,
)
from app.schemas.semantic_search import SemanticSearchItem, SemanticSearchRequest
from app.schemas.text_search import TextSearchItem, TextSearchRequest
from app.services.semantic_index_service import SemanticIndexService, SemanticServiceError
from app.services.semantic_search_service import SemanticSearchService
from app.services.text_search_service import TextSearchService, TextSearchValidationError
from app.services.document_governance_service import DocumentGovernanceService
from app.services.embedding_runtime_service import (
    EmbeddingRuntimeService,
    get_embedding_runtime_service,
)


class HybridSearchError(RuntimeError):
    """Error estable y seguro del flujo híbrido."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _CombinedCandidate:
    text_item: TextSearchItem | None = None
    semantic_item: SemanticSearchItem | None = None
    text_rank: int | None = None
    semantic_rank: int | None = None
    hybrid_score: float = 0.0


class HybridSearchService:
    """Ejecuta ambas fuentes secuencialmente y fusiona sus posiciones."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        text_service: TextSearchService | None = None,
        semantic_service: SemanticSearchService | None = None,
        repository: SemanticChunkRepository | None = None,
        embedding_runtime: EmbeddingRuntimeService | None = None,
    ) -> None:
        index_service = SemanticIndexService(session)
        self.text_service = text_service or TextSearchService(session)
        self.semantic_service = semantic_service or SemanticSearchService(index_service)
        self.repository = repository or index_service.repository
        self.governance = DocumentGovernanceService()
        self.embedding_runtime = (
            embedding_runtime
            if embedding_runtime is not None
            else get_embedding_runtime_service()
            if semantic_service is None
            else None
        )

    async def search(
        self,
        request: HybridSearchRequest,
        *,
        request_id: str | None = None,
    ) -> HybridSearchResponse:
        started_at = time.perf_counter()
        candidate_limit = self._candidate_limit(request.top_k)
        log_info(
            "Iniciando búsqueda híbrida local",
            operation="hybrid_search",
            request_id=request_id,
            text_match_mode=request.text_match_mode.value,
            query_length=len(request.query),
            term_count=len(request.query.split()),
            top_k=request.top_k,
            candidate_limit=candidate_limit,
            filter_count=self._filter_count(request),
        )
        try:
            text_response = await self.text_service.search(
                TextSearchRequest(
                    query=request.query,
                    match_mode=request.text_match_mode,
                    document_id=request.document_id,
                    document_types=request.document_types,
                    knowledge_layers=request.knowledge_layers,
                    min_page=request.min_page,
                    max_page=request.max_page,
                    page=1,
                    page_size=candidate_limit,
                ),
                request_id=request_id,
            )
            if self.embedding_runtime is None:
                semantic_response = await self.semantic_service.search(
                    SemanticSearchRequest(
                        query=request.query,
                        top_k=candidate_limit,
                        document_id=request.document_id,
                        document_types=request.document_types,
                        knowledge_layers=request.knowledge_layers,
                        min_page=request.min_page,
                        max_page=request.max_page,
                    ),
                    request_id=request_id,
                )
            else:
                async with self.embedding_runtime.activity():
                    semantic_response = await self.semantic_service.search(
                        SemanticSearchRequest(
                            query=request.query,
                            top_k=candidate_limit,
                            document_id=request.document_id,
                            document_types=request.document_types,
                            knowledge_layers=request.knowledge_layers,
                            min_page=request.min_page,
                            max_page=request.max_page,
                        ),
                        request_id=request_id,
                    )
            combined = self._fuse(text_response.items, semantic_response.items)
            validated, stale_count = await self._validate_against_sqlite(
                combined, request
            )
        except HybridSearchError as exc:
            self._log_error(exc.code, request, request_id, started_at)
            raise
        except EmbeddingError as exc:
            self._log_error(exc.code, request, request_id, started_at)
            raise SemanticServiceError(exc.code) from exc
        except (TextSearchRepositoryError, SemanticServiceError) as exc:
            self._log_error(exc.code, request, request_id, started_at)
            raise
        except TextSearchValidationError as exc:
            self._log_error("HYBRID_OUTPUT_INVALID", request, request_id, started_at)
            raise HybridSearchError("HYBRID_OUTPUT_INVALID") from exc
        except Exception as exc:
            self._log_error("HYBRID_SEARCH_ERROR", request, request_id, started_at)
            raise HybridSearchError("HYBRID_SEARCH_ERROR") from exc

        ordered = sorted(validated, key=self._sort_key)[: request.top_k]
        response = HybridSearchResponse(
            items=[self._response_item(value) for value in ordered],
            returned=len(ordered),
            top_k=request.top_k,
        )
        log_success(
            "Búsqueda híbrida local completada",
            operation="hybrid_search",
            request_id=request_id,
            text_match_mode=request.text_match_mode.value,
            query_length=len(request.query),
            term_count=len(request.query.split()),
            top_k=request.top_k,
            candidate_limit=candidate_limit,
            filter_count=self._filter_count(request),
            text_candidates=len(text_response.items),
            semantic_candidates=len(semantic_response.items),
            combined_candidates=len(combined),
            stale_discarded=stale_count,
            returned=len(ordered),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return response

    @staticmethod
    def _candidate_limit(top_k: int) -> int:
        return min(
            top_k * settings.hybrid_candidate_multiplier,
            settings.hybrid_top_k_max * settings.hybrid_candidate_multiplier,
            settings.text_search_max_page_size,
            settings.semantic_search_top_k_max,
        )

    @staticmethod
    def _fuse(
        text_items: list[TextSearchItem],
        semantic_items: list[SemanticSearchItem],
    ) -> dict[UUID, _CombinedCandidate]:
        combined: dict[UUID, _CombinedCandidate] = {}
        seen_text: set[UUID] = set()
        for rank, text_item in enumerate(text_items, start=1):
            if not math.isfinite(text_item.rank_bm25):
                raise HybridSearchError("HYBRID_OUTPUT_INVALID")
            if text_item.chunk_id in seen_text:
                continue
            seen_text.add(text_item.chunk_id)
            candidate = combined.setdefault(text_item.chunk_id, _CombinedCandidate())
            candidate.text_item = text_item
            candidate.text_rank = rank
            candidate.hybrid_score += settings.hybrid_text_weight / (
                settings.hybrid_rrf_k + rank
            )
        seen_semantic: set[UUID] = set()
        for rank, semantic_item in enumerate(semantic_items, start=1):
            if not math.isfinite(semantic_item.distance_cosine):
                raise HybridSearchError("HYBRID_OUTPUT_INVALID")
            if semantic_item.chunk_id in seen_semantic:
                continue
            seen_semantic.add(semantic_item.chunk_id)
            candidate = combined.setdefault(semantic_item.chunk_id, _CombinedCandidate())
            candidate.semantic_item = semantic_item
            candidate.semantic_rank = rank
            candidate.hybrid_score += settings.hybrid_semantic_weight / (
                settings.hybrid_rrf_k + rank
            )
        if any(
            not math.isfinite(candidate.hybrid_score) or candidate.hybrid_score <= 0
            for candidate in combined.values()
        ):
            raise HybridSearchError("HYBRID_OUTPUT_INVALID")
        return combined

    async def _validate_against_sqlite(
        self,
        combined: dict[UUID, _CombinedCandidate],
        request: HybridSearchRequest,
    ) -> tuple[list[tuple[_CombinedCandidate, ActiveChunk]], int]:
        active = await self.repository.get_active_by_ids(list(combined))
        validated: list[tuple[_CombinedCandidate, ActiveChunk]] = []
        stale = 0
        for chunk_id, candidate in combined.items():
            chunk = active.get(chunk_id)
            source_items = [
                item
                for item in (candidate.text_item, candidate.semantic_item)
                if item is not None
            ]
            if (
                chunk is None
                or any(not self._metadata_matches(item, chunk) for item in source_items)
                or not self._filters_match(request, chunk)
                or not self.governance.evaluate_rag_eligibility(
                    chunk.governance
                ).eligible
            ):
                stale += 1
                continue
            validated.append((candidate, chunk))
        return validated, stale

    @staticmethod
    def _metadata_matches(
        item: TextSearchItem | SemanticSearchItem,
        chunk: ActiveChunk,
    ) -> bool:
        return (
            item.document_id == chunk.document_id
            and item.document_type == chunk.document_type
            and item.knowledge_layer == chunk.knowledge_layer
            and item.chunk_index == chunk.chunk_index
            and item.start_page == chunk.start_page
            and item.end_page == chunk.end_page
        )

    @staticmethod
    def _filters_match(request: HybridSearchRequest, chunk: ActiveChunk) -> bool:
        if request.document_id is not None and chunk.document_id != request.document_id:
            return False
        if request.document_types and chunk.document_type not in request.document_types:
            return False
        if request.knowledge_layers and chunk.knowledge_layer not in request.knowledge_layers:
            return False
        if request.min_page is not None and chunk.start_page < request.min_page:
            return False
        return not (request.max_page is not None and chunk.end_page > request.max_page)

    @staticmethod
    def _sort_key(
        value: tuple[_CombinedCandidate, ActiveChunk],
    ) -> tuple[float, int, int, str, int, str]:
        candidate, chunk = value
        both = candidate.text_rank is not None and candidate.semantic_rank is not None
        ranks = [
            rank
            for rank in (candidate.text_rank, candidate.semantic_rank)
            if rank is not None
        ]
        return (
            -candidate.hybrid_score,
            -int(both),
            min(ranks),
            str(chunk.document_id),
            chunk.chunk_index,
            str(chunk.chunk_id),
        )

    @staticmethod
    def _response_item(
        value: tuple[_CombinedCandidate, ActiveChunk],
    ) -> HybridSearchItem:
        candidate, chunk = value
        return HybridSearchItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=chunk.document_name or "Documento",
            document_type=chunk.document_type,
            knowledge_layer=chunk.knowledge_layer,
            chunk_index=chunk.chunk_index,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            snippet=SemanticSearchService._snippet(chunk.text),
            hybrid_score=candidate.hybrid_score,
            appeared_in_text=candidate.text_rank is not None,
            appeared_in_semantic=candidate.semantic_rank is not None,
            text_rank=candidate.text_rank,
            semantic_rank=candidate.semantic_rank,
            rank_bm25=(
                candidate.text_item.rank_bm25
                if candidate.text_item is not None
                else None
            ),
            distance_cosine=(
                candidate.semantic_item.distance_cosine
                if candidate.semantic_item is not None
                else None
            ),
        )

    @staticmethod
    def _filter_count(request: HybridSearchRequest) -> int:
        return sum(
            value is not None
            for value in (
                request.document_id,
                request.document_types,
                request.knowledge_layers,
                request.min_page,
                request.max_page,
            )
        )

    @staticmethod
    def _log_error(
        code: str,
        request: HybridSearchRequest,
        request_id: str | None,
        started_at: float,
    ) -> None:
        log_error(
            "Falló la búsqueda híbrida local",
            operation="hybrid_search",
            request_id=request_id,
            text_match_mode=request.text_match_mode.value,
            query_length=len(request.query),
            term_count=len(request.query.split()),
            top_k=request.top_k,
            filter_count=HybridSearchService._filter_count(request),
            error_code=code,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
