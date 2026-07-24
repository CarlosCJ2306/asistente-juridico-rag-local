"""Operaciones de persistencia para chunks jurídicos."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    """Repositorio sin commit implícito para chunks documentales."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(self, chunks: list[DocumentChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def list_by_document(self, document_id: UUID, *, offset: int, limit: int) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def count_by_document(self, document_id: UUID) -> int:
        statement = select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id)
        return int((await self.session.scalar(statement)) or 0)

    async def delete_by_document(self, document_id: UUID) -> None:
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
