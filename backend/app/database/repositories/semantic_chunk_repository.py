"""Lectura de chunks activos para indexación y validación semántica."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models.document import Document, DocumentType, KnowledgeLayer
from app.database.models.document_chunk import DocumentChunk
from app.services.document_governance_service import (
    DocumentGovernanceService,
    DocumentGovernanceSnapshot,
)


@dataclass(frozen=True)
class ActiveChunk:
    chunk_id: UUID
    document_id: UUID
    document_type: DocumentType
    chunk_index: int
    text: str
    start_page: int
    end_page: int
    document_name: str = ""
    governance: DocumentGovernanceSnapshot = DocumentGovernanceSnapshot()

    @property
    def knowledge_layer(self) -> KnowledgeLayer:
        return self.governance.knowledge_layer


@dataclass(frozen=True)
class ActiveSourceSnapshot:
    chunk_count: int
    fingerprint: str


class FingerprintDigest(Protocol):
    def update(self, data: bytes) -> None: ...


def update_source_fingerprint(digest: FingerprintDigest, chunk: ActiveChunk) -> None:
    """Añade un chunk al hash canónico sin conservar su contenido."""

    values = (
        f"semantic_metadata_schema:{settings.semantic_index_schema_version}",
        chunk.chunk_id.hex,
        chunk.document_id.hex,
        chunk.document_type.value,
        chunk.knowledge_layer.value,
        chunk.governance.review_status.value,
        chunk.governance.legal_validity_status.value,
        chunk.governance.status.value,
        "1" if chunk.governance.is_deleted else "0",
        chunk.governance.expires_at.isoformat()
        if chunk.governance.expires_at is not None
        else "",
        chunk.governance.archived_at.isoformat()
        if chunk.governance.archived_at is not None
        else "",
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
            select(
                DocumentChunk,
                Document,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
        )

    async def count_active(self) -> int:
        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
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
        return [
            self._to_active(chunk, document)
            for chunk, document in rows
        ]

    async def get_active_by_ids(self, chunk_ids: list[UUID]) -> dict[UUID, ActiveChunk]:
        if not chunk_ids:
            return {}
        statement = self._active_statement().where(DocumentChunk.id.in_(chunk_ids))
        rows = (await self.session.execute(statement)).all()
        return {
            chunk.id: self._to_active(chunk, document)
            for chunk, document in rows
        }

    async def get_documents_by_ids(
        self,
        document_ids: list[UUID],
    ) -> dict[UUID, Document]:
        """Carga documentos en un solo query para transiciones de indexación."""

        if not document_ids:
            return {}
        documents = await self.session.scalars(
            select(Document).where(Document.id.in_(document_ids))
        )
        return {document.id: document for document in documents.all()}

    async def source_snapshot(
        self,
        *,
        batch_size: int,
        now: datetime | None = None,
    ) -> ActiveSourceSnapshot:
        """Calcula un fingerprint determinista por lotes sin modificar SQLite."""

        digest = hashlib.sha256()
        governance = DocumentGovernanceService()
        effective_now = now or datetime.now(timezone.utc)
        offset = 0
        chunk_count = 0
        while True:
            chunks = await self.list_active_batch(offset=offset, limit=batch_size)
            if not chunks:
                break
            for chunk in chunks:
                if not governance.evaluate_indexing_eligibility(
                    chunk.governance,
                    now=effective_now,
                ).eligible:
                    continue
                update_source_fingerprint(digest, chunk)
                chunk_count += 1
            offset += len(chunks)
        return ActiveSourceSnapshot(
            chunk_count=chunk_count,
            fingerprint=digest.hexdigest(),
        )

    @staticmethod
    def _to_active(
        chunk: DocumentChunk,
        document: Document,
    ) -> ActiveChunk:
        return ActiveChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_type=document.document_type,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            document_name=document.display_name,
            governance=DocumentGovernanceSnapshot.from_document(document),
        )
