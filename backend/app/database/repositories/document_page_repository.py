"""Operaciones de persistencia para páginas extraídas."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document_page import DocumentPage


class DocumentPageRepository:
    """Repositorio sin commit implícito para páginas documentales."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(self, pages: list[DocumentPage]) -> None:
        self.session.add_all(pages)
        await self.session.flush()

    async def list_by_document(self, document_id: UUID, *, offset: int, limit: int) -> list[DocumentPage]:
        statement = (
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def count_by_document(self, document_id: UUID) -> int:
        statement = select(func.count()).select_from(DocumentPage).where(DocumentPage.document_id == document_id)
        return int((await self.session.scalar(statement)) or 0)

    async def delete_by_document(self, document_id: UUID) -> None:
        await self.session.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
