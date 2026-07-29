"""Repositorio asíncrono de pertenencia documental explícita."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.document_domain import (
    CaseDocument,
    CaseDocumentPurpose,
    CaseDocumentSnapshot,
)
from app.database.models.case_document import CaseDocumentRecord
from app.documents import DocumentCatalogFacade, DocumentRead


class DuplicateActiveCaseDocumentError(RuntimeError):
    """La pareja Case/Document ya tiene una asociación activa."""


class CaseDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._catalog = DocumentCatalogFacade(session)

    async def create_association(self, association: CaseDocument) -> None:
        self.session.add(self._record(association))
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateActiveCaseDocumentError from exc

    async def get_active_by_public_id(
        self, public_id: UUID, *, case_id: UUID
    ) -> CaseDocument | None:
        record = await self.session.scalar(
            select(CaseDocumentRecord).where(
                CaseDocumentRecord.public_id == public_id,
                CaseDocumentRecord.case_id == case_id,
                CaseDocumentRecord.removed_at.is_(None),
            )
        )
        return None if record is None else self._domain(record)

    async def get_active_by_case_and_document(
        self, case_id: UUID, document_id: UUID
    ) -> CaseDocument | None:
        record = await self.session.scalar(
            select(CaseDocumentRecord).where(
                CaseDocumentRecord.case_id == case_id,
                CaseDocumentRecord.document_id == document_id,
                CaseDocumentRecord.removed_at.is_(None),
            )
        )
        return None if record is None else self._domain(record)

    async def detect_duplicate_active(self, case_id: UUID, document_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(CaseDocumentRecord.id).where(
                    CaseDocumentRecord.case_id == case_id,
                    CaseDocumentRecord.document_id == document_id,
                    CaseDocumentRecord.removed_at.is_(None),
                )
            )
        ) is not None

    async def list_active_by_case_paginated(
        self, case_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[CaseDocument], int]:
        active = CaseDocumentRecord.removed_at.is_(None)
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(CaseDocumentRecord).where(
                        CaseDocumentRecord.case_id == case_id, active
                    )
                )
            )
            or 0
        )
        rows = await self.session.scalars(
            select(CaseDocumentRecord)
            .where(CaseDocumentRecord.case_id == case_id, active)
            .order_by(
                CaseDocumentRecord.display_order,
                CaseDocumentRecord.attached_at,
                CaseDocumentRecord.public_id,
            )
            .offset(offset)
            .limit(limit)
        )
        return [self._domain(record) for record in rows.all()], total

    async def count_active_by_case(self, case_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(CaseDocumentRecord).where(
                        CaseDocumentRecord.case_id == case_id,
                        CaseDocumentRecord.removed_at.is_(None),
                    )
                )
            )
            or 0
        )

    async def update_purpose_and_order(
        self, association: CaseDocument, *, expected_version: int
    ) -> bool:
        return await self._update(association, expected_version=expected_version)

    async def soft_remove(
        self, association: CaseDocument, *, expected_version: int
    ) -> bool:
        return await self._update(association, expected_version=expected_version)

    async def resolve_documents_batch(
        self, document_ids: tuple[UUID, ...]
    ) -> dict[UUID, DocumentRead]:
        batch = await self._catalog.resolve_many(document_ids, include_deleted=True)
        return {document.id: document for document in batch.items}

    async def _update(
        self, association: CaseDocument, *, expected_version: int
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                update(CaseDocumentRecord)
                .where(
                    CaseDocumentRecord.id == association.id,
                    CaseDocumentRecord.version == expected_version,
                    CaseDocumentRecord.removed_at.is_(None),
                )
                .values(**self._values(association))
            ),
        )
        return result.rowcount == 1

    @staticmethod
    def _record(association: CaseDocument) -> CaseDocumentRecord:
        return CaseDocumentRecord(
            id=association.id,
            public_id=association.public_id,
            case_id=association.case_id,
            document_id=association.document_id,
            **CaseDocumentRepository._values(association),
        )

    @staticmethod
    def _values(association: CaseDocument) -> dict[str, object]:
        snapshot = association.snapshot
        return {
            "purpose": association.purpose.value,
            "display_order": association.display_order,
            "snapshot_display_name": snapshot.display_name,
            "snapshot_document_type": snapshot.document_type,
            "snapshot_knowledge_layer": snapshot.knowledge_layer,
            "snapshot_source_kind": snapshot.source_kind,
            "snapshot_review_status": snapshot.review_status,
            "snapshot_legal_validity_status": snapshot.legal_validity_status,
            "snapshot_extraction_status": snapshot.extraction_status,
            "snapshot_index_status": snapshot.index_status,
            "snapshot_expires_at": snapshot.expires_at,
            "snapshot_document_updated_at": snapshot.document_updated_at,
            "snapshot_document_version_label": snapshot.document_version_label,
            "version": association.version,
            "attached_at": association.attached_at,
            "updated_at": association.updated_at,
            "removed_at": association.removed_at,
        }

    @staticmethod
    def _domain(record: CaseDocumentRecord) -> CaseDocument:
        return CaseDocument(
            id=record.id,
            public_id=record.public_id,
            case_id=record.case_id,
            document_id=record.document_id,
            purpose=CaseDocumentPurpose(record.purpose),
            display_order=record.display_order,
            snapshot=CaseDocumentSnapshot(
                display_name=record.snapshot_display_name,
                document_type=record.snapshot_document_type,
                knowledge_layer=record.snapshot_knowledge_layer,
                source_kind=record.snapshot_source_kind,
                review_status=record.snapshot_review_status,
                legal_validity_status=record.snapshot_legal_validity_status,
                extraction_status=record.snapshot_extraction_status,
                index_status=record.snapshot_index_status,
                expires_at=record.snapshot_expires_at,
                document_updated_at=record.snapshot_document_updated_at,
                document_version_label=record.snapshot_document_version_label,
            ),
            version=record.version,
            attached_at=record.attached_at,
            updated_at=record.updated_at,
            removed_at=record.removed_at,
        )
