"""Servicio autoritativo de pertenencia documental del expediente."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.document_domain import (
    CaseDocument,
    CaseDocumentAvailability,
    CaseDocumentDomainError,
    CaseDocumentSnapshot,
    CaseDocumentWarning,
)
from app.cases.document_repository import (
    CaseDocumentRepository,
    DuplicateActiveCaseDocumentError,
)
from app.cases.errors import CaseError
from app.cases.repository import CaseRepository
from app.cases.service import CaseService
from app.core.Log import log_success
from app.core.config import settings
from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    RagEligibilityReason,
)
from app.documents import DocumentRead
from app.schemas.case_document import (
    CaseDocumentAttach,
    CaseDocumentListResponse,
    CaseDocumentPublic,
    CaseDocumentRemove,
    CaseDocumentUpdate,
)
from app.services.conversation_principal import ConversationPrincipal


_ALLOWED_LAYERS = frozenset(
    {KnowledgeLayer.PRIVATE_LIBRARY, KnowledgeLayer.TEMPORARY}
)
_PENDING_DOCUMENT_STATUSES = frozenset(
    {
        DocumentStatus.REGISTERED,
        DocumentStatus.STORED,
        DocumentStatus.PENDING_EXTRACTION,
        DocumentStatus.EXTRACTING,
    }
)
_PENDING_INDEX_STATUSES = frozenset(
    {IndexStatus.NOT_REQUESTED, IndexStatus.PENDING, IndexStatus.INDEXING}
)


class CaseDocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CaseDocumentRepository(session)
        self.case_repository = CaseRepository(session)
        self.case_service = CaseService(session)

    async def attach_document(
        self,
        case_public_id: UUID,
        payload: CaseDocumentAttach,
        principal: ConversationPrincipal,
    ) -> CaseDocumentPublic:
        case = await self._mutable_case(
            case_public_id, principal, expected_version=payload.expected_case_version
        )
        documents = await self.repository.resolve_documents_batch((payload.document_id,))
        document = documents.get(payload.document_id)
        self._validate_attachable(document)
        assert document is not None
        if await self.repository.detect_duplicate_active(case.id, document.id):
            raise CaseError("CASE_DOCUMENT_DUPLICATE")
        now = self._now()
        association = CaseDocument.create(
            case_id=case.id,
            document_id=document.id,
            purpose=payload.purpose,
            display_order=payload.display_order,
            snapshot=self._snapshot(document),
            now=now,
        )
        updated_case = case.touch(
            now=now, retention_days=settings.conversation_guest_retention_days
        )
        try:
            await self.repository.create_association(association)
            if not await self.case_repository.update(
                updated_case,
                expected_version=payload.expected_case_version,
                event_type="document_attached",
                from_status=None,
            ):
                raise CaseError("CASE_VERSION_CONFLICT")
            await self.session.commit()
        except DuplicateActiveCaseDocumentError as exc:
            await self.session.rollback()
            raise CaseError("CASE_DOCUMENT_DUPLICATE") from exc
        except CaseError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            raise CaseError("CASE_DOCUMENT_ATTACH_FAILED") from exc
        log_success(
            "Documento asociado al caso",
            operation="case_document_attach",
            purpose=association.purpose.value,
            version=association.version,
        )
        return self._public(association, document, updated_case.version, False)

    async def list_documents(
        self,
        case_public_id: UUID,
        principal: ConversationPrincipal,
        *,
        page: int,
        page_size: int,
    ) -> CaseDocumentListResponse:
        case = await self.case_service.resolve_owned_case(case_public_id, principal)
        associations, total = await self.repository.list_active_by_case_paginated(
            case.id, offset=(page - 1) * page_size, limit=page_size
        )
        documents = await self.repository.resolve_documents_batch(
            tuple(link.document_id for link in associations)
        )
        return CaseDocumentListResponse(
            items=[
                self._public(
                    link,
                    documents.get(link.document_id),
                    case.version,
                    case.read_only,
                )
                for link in associations
            ],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
            case_version=case.version,
        )

    async def get_document(
        self,
        case_public_id: UUID,
        association_public_id: UUID,
        principal: ConversationPrincipal,
    ) -> CaseDocumentPublic:
        case = await self.case_service.resolve_owned_case(case_public_id, principal)
        association = await self._association(association_public_id, case.id)
        documents = await self.repository.resolve_documents_batch(
            (association.document_id,)
        )
        return self._public(
            association,
            documents.get(association.document_id),
            case.version,
            case.read_only,
        )

    async def update_document(
        self,
        case_public_id: UUID,
        association_public_id: UUID,
        payload: CaseDocumentUpdate,
        principal: ConversationPrincipal,
    ) -> CaseDocumentPublic:
        case = await self._mutable_case(
            case_public_id, principal, expected_version=payload.expected_case_version
        )
        association = await self._association(association_public_id, case.id)
        self._require_link_version(
            association, payload.expected_document_link_version
        )
        now = self._now()
        try:
            updated = association.update_link(
                purpose=payload.purpose,
                display_order=payload.display_order,
                now=now,
            )
        except CaseDocumentDomainError as exc:
            raise CaseError(exc.code) from exc
        updated_case = case.touch(
            now=now, retention_days=settings.conversation_guest_retention_days
        )
        try:
            if not await self.repository.update_purpose_and_order(
                updated, expected_version=payload.expected_document_link_version
            ):
                raise CaseError("CASE_DOCUMENT_VERSION_CONFLICT")
            if not await self.case_repository.update(
                updated_case,
                expected_version=payload.expected_case_version,
                event_type="document_link_updated",
                from_status=None,
            ):
                raise CaseError("CASE_VERSION_CONFLICT")
            await self.session.commit()
        except CaseError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            raise CaseError("CASE_DOCUMENT_UPDATE_FAILED") from exc
        documents = await self.repository.resolve_documents_batch((updated.document_id,))
        log_success(
            "Asociación documental actualizada",
            operation="case_document_update",
            purpose=updated.purpose.value,
            version=updated.version,
        )
        return self._public(
            updated, documents.get(updated.document_id), updated_case.version, False
        )

    async def remove_document(
        self,
        case_public_id: UUID,
        association_public_id: UUID,
        payload: CaseDocumentRemove,
        principal: ConversationPrincipal,
    ) -> None:
        case = await self._mutable_case(
            case_public_id, principal, expected_version=payload.expected_case_version
        )
        association = await self._association(association_public_id, case.id)
        self._require_link_version(
            association, payload.expected_document_link_version
        )
        now = self._now()
        removed = association.remove(now=now)
        updated_case = case.touch(
            now=now, retention_days=settings.conversation_guest_retention_days
        )
        try:
            if not await self.repository.soft_remove(
                removed, expected_version=payload.expected_document_link_version
            ):
                raise CaseError("CASE_DOCUMENT_VERSION_CONFLICT")
            if not await self.case_repository.update(
                updated_case,
                expected_version=payload.expected_case_version,
                event_type="document_removed",
                from_status=None,
            ):
                raise CaseError("CASE_VERSION_CONFLICT")
            await self.session.commit()
        except CaseError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            raise CaseError("CASE_DOCUMENT_REMOVE_FAILED") from exc
        log_success(
            "Documento retirado del caso",
            operation="case_document_remove",
            version=removed.version,
        )

    async def _mutable_case(
        self,
        public_id: UUID,
        principal: ConversationPrincipal,
        *,
        expected_version: int,
    ):
        case = await self.case_service.resolve_owned_case(public_id, principal)
        if case.read_only:
            raise CaseError("CASE_ARCHIVED_READ_ONLY")
        if case.version != expected_version:
            raise CaseError("CASE_VERSION_CONFLICT")
        return case

    async def _association(
        self, association_public_id: UUID, case_id: UUID
    ) -> CaseDocument:
        association = await self.repository.get_active_by_public_id(
            association_public_id, case_id=case_id
        )
        if association is None:
            raise CaseError("CASE_DOCUMENT_NOT_FOUND")
        return association

    @staticmethod
    def _require_link_version(association: CaseDocument, expected: int) -> None:
        if association.version != expected:
            raise CaseError("CASE_DOCUMENT_VERSION_CONFLICT")

    @staticmethod
    def _validate_attachable(document: DocumentRead | None) -> None:
        if document is None:
            raise CaseError("CASE_DOCUMENT_UNAVAILABLE")
        reasons = set(document.rag_eligibility_reasons)
        if (
            RagEligibilityReason.DOCUMENT_DELETED in reasons
            or RagEligibilityReason.DOCUMENT_ARCHIVED in reasons
            or document.status is DocumentStatus.ARCHIVED
            or document.archived_at is not None
        ):
            raise CaseError("CASE_DOCUMENT_UNAVAILABLE")
        if document.is_expired:
            raise CaseError("CASE_DOCUMENT_EXPIRED")
        if document.knowledge_layer not in _ALLOWED_LAYERS:
            raise CaseError("CASE_DOCUMENT_LAYER_NOT_ALLOWED")

    @staticmethod
    def _snapshot(document: DocumentRead) -> CaseDocumentSnapshot:
        return CaseDocumentSnapshot(
            display_name=document.display_name,
            document_type=document.document_type.value,
            knowledge_layer=document.knowledge_layer.value,
            source_kind=document.source_kind.value,
            review_status=document.review_status.value,
            legal_validity_status=document.legal_validity_status.value,
            extraction_status=document.status.value,
            index_status=document.index_status.value,
            expires_at=document.expires_at,
            document_updated_at=document.updated_at,
            document_version_label=document.version_label,
        )

    @classmethod
    def _health(
        cls, association: CaseDocument, document: DocumentRead | None
    ) -> tuple[CaseDocumentAvailability, list[CaseDocumentWarning]]:
        if document is None:
            return (
                CaseDocumentAvailability.UNAVAILABLE,
                [CaseDocumentWarning.DOCUMENT_UNAVAILABLE],
            )
        reasons = set(document.rag_eligibility_reasons)
        warnings: list[CaseDocumentWarning] = []
        if document.knowledge_layer not in _ALLOWED_LAYERS:
            warnings.append(CaseDocumentWarning.LAYER_NOT_ALLOWED)
            availability = CaseDocumentAvailability.UNAVAILABLE
        elif (
            RagEligibilityReason.DOCUMENT_DELETED in reasons
            or RagEligibilityReason.DOCUMENT_ARCHIVED in reasons
            or document.status is DocumentStatus.ARCHIVED
            or document.archived_at is not None
        ):
            warnings.append(CaseDocumentWarning.DOCUMENT_UNAVAILABLE)
            availability = CaseDocumentAvailability.UNAVAILABLE
        elif document.is_expired:
            warnings.append(CaseDocumentWarning.DOCUMENT_EXPIRED)
            availability = CaseDocumentAvailability.EXPIRED
        elif association.snapshot != cls._snapshot(document):
            warnings.append(CaseDocumentWarning.SNAPSHOT_CHANGED)
            availability = CaseDocumentAvailability.STALE
        elif (
            document.status in _PENDING_DOCUMENT_STATUSES
            or document.index_status in _PENDING_INDEX_STATUSES
        ):
            warnings.append(CaseDocumentWarning.PROCESSING_PENDING)
            availability = CaseDocumentAvailability.PENDING_PROCESSING
        elif (
            document.status is not DocumentStatus.EXTRACTED
            or document.index_status is not IndexStatus.INDEXED
        ):
            warnings.append(CaseDocumentWarning.DOCUMENT_UNAVAILABLE)
            availability = CaseDocumentAvailability.UNAVAILABLE
        else:
            availability = CaseDocumentAvailability.AVAILABLE
        if not document.rag_eligible:
            warnings.append(CaseDocumentWarning.RAG_INELIGIBLE)
        return availability, list(dict.fromkeys(warnings))

    @classmethod
    def _public(
        cls,
        association: CaseDocument,
        document: DocumentRead | None,
        case_version: int,
        case_read_only: bool,
    ) -> CaseDocumentPublic:
        availability, warnings = cls._health(association, document)
        snapshot = association.snapshot
        return CaseDocumentPublic(
            association_id=association.public_id,
            document_id=association.document_id,
            display_name=(document.display_name if document else snapshot.display_name),
            document_type=(
                document.document_type
                if document
                else DocumentType(snapshot.document_type)
            ),
            knowledge_layer=(
                document.knowledge_layer
                if document
                else KnowledgeLayer(snapshot.knowledge_layer)
            ),
            purpose=association.purpose,
            display_order=association.display_order,
            availability=availability,
            extraction_status=(
                document.status
                if document
                else DocumentStatus(snapshot.extraction_status)
            ),
            index_status=(
                document.index_status
                if document
                else IndexStatus(snapshot.index_status)
            ),
            rag_eligible=document.rag_eligible if document else False,
            rag_ineligibility_reasons=(
                document.rag_eligibility_reasons
                if document
                else [RagEligibilityReason.DOCUMENT_DELETED]
            ),
            warnings=warnings,
            expires_at=document.expires_at if document else snapshot.expires_at,
            version=association.version,
            case_version=case_version,
            attached_at=association.attached_at,
            updated_at=association.updated_at,
            read_only=case_read_only,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
