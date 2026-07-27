"""Persistencia mínima de claves del corpus administrado."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import Document
from app.database.models.managed_corpus import ManagedCorpusEntry


class ManagedCorpusRepository:
    """Vincula claves de manifiesto sin duplicar metadatos documentales."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_entry(
        self, corpus_id: str, source_key: str
    ) -> ManagedCorpusEntry | None:
        return await self.session.get(ManagedCorpusEntry, (corpus_id, source_key))

    async def get_document(
        self, corpus_id: str, source_key: str
    ) -> Document | None:
        statement = (
            select(Document)
            .join(ManagedCorpusEntry, ManagedCorpusEntry.document_id == Document.id)
            .where(
                ManagedCorpusEntry.corpus_id == corpus_id,
                ManagedCorpusEntry.source_key == source_key,
            )
        )
        return await self.session.scalar(statement)

    async def get_entry_by_document(
        self, document_id: UUID
    ) -> ManagedCorpusEntry | None:
        statement = select(ManagedCorpusEntry).where(
            ManagedCorpusEntry.document_id == document_id
        )
        return await self.session.scalar(statement)

    async def create_entry(
        self,
        *,
        corpus_id: str,
        source_key: str,
        document_id: UUID,
    ) -> ManagedCorpusEntry:
        entry = ManagedCorpusEntry(
            corpus_id=corpus_id,
            source_key=source_key,
            document_id=document_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
