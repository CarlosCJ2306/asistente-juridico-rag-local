"""Reglas de consulta y presentación segura para búsqueda FTS5 local."""

from __future__ import annotations

import html
import re
import time
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_error, log_info, log_success
from app.core.config import settings
from app.database.repositories.text_search_repository import (
    TextSearchRepository,
    TextSearchRepositoryError,
)
from app.database.repositories.semantic_chunk_repository import (
    ActiveChunk,
    SemanticChunkRepository,
)
from app.schemas.text_search import TextMatchMode, TextSearchItem, TextSearchPage, TextSearchRequest
from app.services.document_governance_service import DocumentGovernanceService


class TextSearchValidationError(ValueError):
    """Entrada de consulta no admisible antes de alcanzar SQLite."""


class TextSearchService:
    """Compila consultas FTS5 cerradas y conserva metadatos seguros en logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = TextSearchRepository(session)
        self.chunks = SemanticChunkRepository(session)
        self.governance = DocumentGovernanceService()

    async def search(self, request: TextSearchRequest, *, request_id: str | None = None) -> TextSearchPage:
        normalized, terms = self._normalize_query(request.query)
        expression = self._compile_match_expression(normalized, terms, request.match_mode)
        started_at = time.perf_counter()
        log_info(
            "Iniciando búsqueda textual local",
            operation="text_search",
            request_id=request_id,
            match_mode=request.match_mode.value,
            query_length=len(normalized),
            term_count=len(terms),
            filter_count=self._filter_count(request),
            page=request.page,
            page_size=request.page_size,
        )
        try:
            rows = await self.repository.search_candidates(
                match_expression=expression,
                document_id=request.document_id,
                document_types=request.document_types,
                knowledge_layers=request.knowledge_layers,
                min_page=request.min_page,
                max_page=request.max_page,
            )
        except TextSearchRepositoryError as exc:
            log_error(
                "Búsqueda textual no disponible",
                operation="text_search",
                request_id=request_id,
                match_mode=request.match_mode.value,
                query_length=len(normalized),
                term_count=len(terms),
                error_code=exc.code,
            )
            raise
        active = await self.chunks.get_active_by_ids([row.chunk_id for row in rows])
        governed = [
            (row, chunk)
            for row in rows
            if (chunk := active.get(row.chunk_id)) is not None
            and self._matches(row, chunk, request)
            and self.governance.evaluate_rag_eligibility(chunk.governance).eligible
        ]
        total = len(governed)
        offset = (request.page - 1) * request.page_size
        page_rows = governed[offset : offset + request.page_size]
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        result = TextSearchPage(
            items=[
                TextSearchItem(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    document_type=row.document_type,
                    knowledge_layer=chunk.knowledge_layer,
                    chunk_index=row.chunk_index,
                    start_page=row.start_page,
                    end_page=row.end_page,
                    snippet=self._safe_snippet(row.snippet),
                    rank_bm25=row.rank_bm25,
                )
                for row, chunk in page_rows
            ],
            total=total,
            page=request.page,
            page_size=request.page_size,
        )
        log_success(
            "Búsqueda textual local completada",
            operation="text_search",
            request_id=request_id,
            match_mode=request.match_mode.value,
            query_length=len(normalized),
            term_count=len(terms),
            filter_count=self._filter_count(request),
            page=request.page,
            page_size=request.page_size,
            result_count=len(page_rows),
            total=total,
            duration_ms=duration_ms,
        )
        return result

    @staticmethod
    def _matches(
        row: object,
        chunk: ActiveChunk,
        request: TextSearchRequest,
    ) -> bool:
        if not all(
            getattr(row, field) == getattr(chunk, field)
            for field in (
                "chunk_id",
                "document_id",
                "document_type",
                "chunk_index",
                "start_page",
                "end_page",
            )
        ):
            return False
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
    def _normalize_query(query: str) -> tuple[str, list[str]]:
        normalized = unicodedata.normalize("NFC", query)
        if any(unicodedata.category(character).startswith("C") for character in normalized):
            raise TextSearchValidationError("TEXT_SEARCH_QUERY_INVALID")
        normalized = " ".join(normalized.split())
        if not normalized:
            raise TextSearchValidationError("TEXT_SEARCH_QUERY_EMPTY")
        if len(normalized) > settings.text_search_query_max_chars:
            raise TextSearchValidationError("TEXT_SEARCH_QUERY_TOO_LONG")
        terms = re.findall(r"\S+", normalized)
        if len(terms) > settings.text_search_max_terms:
            raise TextSearchValidationError("TEXT_SEARCH_TOO_MANY_TERMS")
        return normalized, terms

    @staticmethod
    def _compile_match_expression(
        normalized: str,
        terms: list[str],
        mode: TextMatchMode,
    ) -> str:
        quoted_terms = [f'"{term.replace("\"", "\"\"")}"' for term in terms]
        if mode is TextMatchMode.PHRASE:
            return f'"{normalized.replace("\"", "\"\"")}"'
        separator = " AND " if mode is TextMatchMode.ALL_TERMS else " OR "
        return separator.join(quoted_terms)

    @staticmethod
    def _safe_snippet(value: str) -> str:
        return html.escape(value, quote=False)[:500]

    @staticmethod
    def _filter_count(request: TextSearchRequest) -> int:
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
