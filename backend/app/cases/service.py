"""Servicio autoritativo del núcleo Case, sin dependencias HPN o documentales."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.domain import Case, CaseDomainError, CaseRetentionMode, CaseStatus
from app.cases.errors import CaseError
from app.cases.repository import CaseRepository
from app.core.Log import log_success
from app.core.config import settings
from app.schemas.case import CaseActionRequest, CaseCreate, CaseListResponse, CasePublic, CaseUpdate
from app.services.conversation_principal import ConversationPrincipal


class CaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CaseRepository(session)

    async def create_case(
        self, payload: CaseCreate, principal: ConversationPrincipal
    ) -> CasePublic:
        guest_hash = (
            principal.guest_session_hash
            if payload.retention_mode is CaseRetentionMode.TEMPORARY
            and principal.owner_type == "guest"
            else None
        )
        try:
            case = Case.create(
                title=payload.title,
                description=payload.description,
                retention_mode=payload.retention_mode,
                owner_key_hash=guest_hash,
                now=self._now(),
                retention_days=settings.conversation_guest_retention_days,
            )
            await self.repository.create(case, event_type="created")
            await self.session.commit()
        except CaseDomainError as exc:
            await self.session.rollback()
            raise CaseError(exc.code) from exc
        except Exception as exc:
            await self.session.rollback()
            raise CaseError("CASE_CREATE_FAILED") from exc
        log_success("Caso creado", operation="case_create", status=case.status.value, version=case.version)
        return self._public(case)

    async def list_cases(
        self,
        principal: ConversationPrincipal,
        *,
        page: int,
        page_size: int,
    ) -> CaseListResponse:
        rows, total = await self.repository.list_accessible_paginated(
            principal,
            now=self._now(),
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return CaseListResponse(
            items=[self._public(case) for case in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_case(
        self, public_id: UUID, principal: ConversationPrincipal
    ) -> CasePublic:
        case = await self._owned(public_id, principal)
        if case.retention_mode is CaseRetentionMode.TEMPORARY:
            touched = case.touch(
                now=self._now(), retention_days=settings.conversation_guest_retention_days
            )
            await self._persist(
                touched,
                expected_version=case.version,
                event_type="activity_renewed",
                from_status=None,
            )
            case = touched
        return self._public(case)

    async def update_case(
        self,
        public_id: UUID,
        payload: CaseUpdate,
        principal: ConversationPrincipal,
    ) -> CasePublic:
        case = await self._owned(public_id, principal)
        self._require_version(case, payload.expected_version)
        try:
            updated = case.update_content(
                title=payload.title,
                description=payload.description,
                description_supplied="description" in payload.model_fields_set,
                now=self._now(),
                retention_days=settings.conversation_guest_retention_days,
            )
        except CaseDomainError as exc:
            raise CaseError(exc.code) from exc
        await self._persist(
            updated,
            expected_version=payload.expected_version,
            event_type="updated",
            from_status=None,
        )
        return self._public(updated)

    async def transition_case(
        self,
        public_id: UUID,
        payload: CaseActionRequest,
        principal: ConversationPrincipal,
        *,
        target: CaseStatus,
    ) -> CasePublic:
        case = await self._owned(public_id, principal)
        self._require_version(case, payload.expected_version)
        try:
            updated = case.transition(
                target=target,
                now=self._now(),
                retention_days=settings.conversation_guest_retention_days,
            )
        except CaseDomainError as exc:
            raise CaseError(exc.code) from exc
        event_type = "archived" if target is CaseStatus.ARCHIVED else "status_changed"
        await self._persist(
            updated,
            expected_version=payload.expected_version,
            event_type=event_type,
            from_status=case.status,
        )
        return self._public(updated)

    async def restore_case(
        self,
        public_id: UUID,
        payload: CaseActionRequest,
        principal: ConversationPrincipal,
    ) -> CasePublic:
        case = await self._owned(public_id, principal)
        self._require_version(case, payload.expected_version)
        try:
            restored = case.restore(
                now=self._now(), retention_days=settings.conversation_guest_retention_days
            )
        except CaseDomainError as exc:
            raise CaseError(exc.code) from exc
        await self._persist(
            restored,
            expected_version=payload.expected_version,
            event_type="restored",
            from_status=case.status,
        )
        return self._public(restored)

    async def delete_case(
        self,
        public_id: UUID,
        expected_version: int,
        principal: ConversationPrincipal,
    ) -> None:
        case = await self._owned(public_id, principal)
        self._require_version(case, expected_version)
        deleted = case.soft_delete(now=self._now())
        await self._persist(
            deleted,
            expected_version=expected_version,
            event_type="soft_deleted",
            from_status=None,
        )

    async def _owned(self, public_id: UUID, principal: ConversationPrincipal) -> Case:
        case = await self.repository.get_owned_by_public_id(public_id, principal)
        if case is None:
            raise CaseError("CASE_NOT_FOUND")
        if case.is_expired(self._now()):
            raise CaseError("CASE_EXPIRED")
        return case

    async def resolve_owned_case(
        self, public_id: UUID, principal: ConversationPrincipal
    ) -> Case:
        """Reutiliza ownership y expiración sin renovar actividad por lectura."""

        return await self._owned(public_id, principal)

    async def _persist(
        self,
        case: Case,
        *,
        expected_version: int,
        event_type: str,
        from_status: CaseStatus | None,
    ) -> None:
        try:
            saved = await self.repository.update(
                case,
                expected_version=expected_version,
                event_type=event_type,
                from_status=from_status,
            )
            if not saved:
                raise CaseError("CASE_VERSION_CONFLICT")
            await self.session.commit()
        except CaseError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            raise CaseError("CASE_UPDATE_FAILED") from exc

    @staticmethod
    def _require_version(case: Case, expected: int) -> None:
        if case.version != expected:
            raise CaseError("CASE_VERSION_CONFLICT")

    @staticmethod
    def _public(case: Case) -> CasePublic:
        return CasePublic(
            public_id=case.public_id,
            title=case.title,
            description=case.description,
            status=case.status.value,
            retention_mode=case.retention_mode,
            expires_at=case.expires_at,
            version=case.version,
            created_at=case.created_at,
            updated_at=case.updated_at,
            archived_at=case.archived_at,
            read_only=case.read_only,
            requires_professional_review=True,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
