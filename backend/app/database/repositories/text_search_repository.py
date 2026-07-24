"""Acceso parametrizado al índice FTS5 derivado de los chunks."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import DocumentType


class TextSearchRepositoryError(RuntimeError):
    """Error estable de disponibilidad o ejecución del índice textual."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TextSearchRow:
    chunk_id: UUID
    document_id: UUID
    document_type: DocumentType
    chunk_index: int
    start_page: int
    end_page: int
    snippet: str
    rank_bm25: float


class TextSearchRepository:
    """Consulta FTS5 sin modificar el índice ni los datos documentales."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        *,
        match_expression: str,
        document_id: UUID | None,
        document_types: list[DocumentType] | None,
        min_page: int | None,
        max_page: int | None,
        offset: int,
        limit: int,
    ) -> tuple[list[TextSearchRow], int]:
        await self._ensure_index_ready()
        where_sql, params = self._where_clause(
            match_expression=match_expression,
            document_id=document_id,
            document_types=document_types,
            min_page=min_page,
            max_page=max_page,
        )
        params.update(offset=offset, limit=limit)
        try:
            count = int(
                (await self.session.scalar(text(f"SELECT COUNT(*) {where_sql}"), params)) or 0
            )
            result = await self.session.execute(
                text(
                    "SELECT f.chunk_id, f.document_id, d.document_type, "
                    "f.chunk_index, f.start_page, f.end_page, "
                    "snippet(document_chunks_fts, 0, '«', '»', '…', 12) AS snippet, "
                    "bm25(document_chunks_fts) AS rank_bm25 "
                    f"{where_sql} "
                    "ORDER BY rank_bm25 ASC, f.document_id ASC, "
                    "f.chunk_index ASC, f.chunk_id ASC "
                    "LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        except OperationalError as exc:
            raise self._classify_error(exc) from exc
        rows = [
            TextSearchRow(
                chunk_id=UUID(str(row.chunk_id)),
                document_id=UUID(str(row.document_id)),
                document_type=DocumentType(row.document_type),
                chunk_index=int(row.chunk_index),
                start_page=int(row.start_page),
                end_page=int(row.end_page),
                snippet=str(row.snippet),
                rank_bm25=float(row.rank_bm25),
            )
            for row in result.mappings()
        ]
        return rows, count

    async def _ensure_index_ready(self) -> None:
        try:
            await self.session.scalar(text("SELECT fts5_source_id()"))
            exists = await self.session.scalar(
                text(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'document_chunks_fts'"
                )
            )
        except OperationalError as exc:
            raise self._classify_error(exc) from exc
        if exists is None:
            raise TextSearchRepositoryError("TEXT_SEARCH_INDEX_NOT_READY")

    @staticmethod
    def _where_clause(
        *,
        match_expression: str,
        document_id: UUID | None,
        document_types: list[DocumentType] | None,
        min_page: int | None,
        max_page: int | None,
    ) -> tuple[str, dict[str, object]]:
        clauses = [
            "FROM document_chunks_fts AS f "
            "JOIN document_chunks AS c ON c.id = f.chunk_id "
            "JOIN documents AS d ON d.id = f.document_id "
            "WHERE document_chunks_fts MATCH :match_expression",
            "AND d.is_deleted = 0",
        ]
        params: dict[str, object] = {"match_expression": match_expression}
        if document_id is not None:
            clauses.append("AND f.document_id = :document_id")
            params["document_id"] = document_id.hex
        if document_types:
            placeholders = []
            for index, document_type in enumerate(document_types):
                key = f"document_type_{index}"
                placeholders.append(f":{key}")
                params[key] = document_type.value
            clauses.append(f"AND d.document_type IN ({', '.join(placeholders)})")
        if min_page is not None:
            clauses.append("AND f.start_page >= :min_page")
            params["min_page"] = min_page
        if max_page is not None:
            clauses.append("AND f.end_page <= :max_page")
            params["max_page"] = max_page
        return " ".join(clauses), params

    @staticmethod
    def _classify_error(error: OperationalError) -> TextSearchRepositoryError:
        detail = str(error.orig).lower() if error.orig is not None else ""
        if "no such module: fts5" in detail or "fts5" in detail and "module" in detail:
            return TextSearchRepositoryError("FTS5_NOT_AVAILABLE")
        if "no such function: fts5_source_id" in detail:
            return TextSearchRepositoryError("FTS5_NOT_AVAILABLE")
        if "no such table" in detail and "document_chunks_fts" in detail:
            return TextSearchRepositoryError("TEXT_SEARCH_INDEX_NOT_READY")
        return TextSearchRepositoryError("TEXT_SEARCH_ERROR")
