"""Lectura de chunks activos para indexación y validación semántica."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document, DocumentType
from app.database.models.document_chunk import DocumentChunk


@dataclass(frozen=True)
class ActiveChunk:
    chunk_id: UUID
    document_id: UUID
    document_type: DocumentType
    chunk_index: int
    text: str
    start_page: int
    end_page: int


@dataclass(frozen=True)
class ActiveSourceSnapshot:
    chunk_count: int
    fingerprint: str


class FingerprintDigest(Protocol):
    def update(self, data: bytes) -> None: ...


def update_source_fingerprint(digest: FingerprintDigest, chunk: ActiveChunk) -> None:
    """Añade un chunk al hash canónico sin conservar su contenido."""

    values = (
        chunk.chunk_id.hex,
        chunk.document_id.hex,
        chunk.document_type.value,
        str(chunk.chunk_index),
        str(chunk.start_page),
        str(chunk.end_page),
        chunk.text,
    )
    for value in values:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big", signed=False))
        digest.update(encoded)


class SemanticChunkRepository:
    """Consulta SQLite sin modificar documentos, chunks ni el índice FTS5."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _active_statement():
        return (
            select(DocumentChunk, Document.document_type)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_deleted.is_(False))
        )

    async def count_active(self) -> int:
        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_deleted.is_(False))
        )
        return int((await self.session.scalar(statement)) or 0)

    async def list_active_batch(self, *, offset: int, limit: int) -> list[ActiveChunk]:
        statement = (
            self._active_statement()
            .order_by(
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.id,
            )
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [self._to_active(chunk, document_type) for chunk, document_type in rows]

    async def get_active_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, ActiveChunk]:
        if not chunk_ids:
            return {}
        statement = self._active_statement().where(DocumentChunk.id.in_(chunk_ids))
        rows = (await self.session.execute(statement)).all()
        return {
            chunk.id: self._to_active(chunk, document_type)
            for chunk, document_type in rows
        }

    async def source_snapshot(self, *, batch_size: int) -> ActiveSourceSnapshot:
        """Calcula un fingerprint determinista por lotes sin modificar SQLite."""

        digest = hashlib.sha256()
        offset = 0
        chunk_count = 0
        while True:
            chunks = await self.list_active_batch(offset=offset, limit=batch_size)
            if not chunks:
                break
            for chunk in chunks:
                update_source_fingerprint(digest, chunk)
            offset += len(chunks)
            chunk_count += len(chunks)
        return ActiveSourceSnapshot(
            chunk_count=chunk_count,
            fingerprint=digest.hexdigest(),
        )

    @staticmethod
    def _to_active(chunk: DocumentChunk, document_type: DocumentType) -> ActiveChunk:
        return ActiveChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_type=document_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
        )
