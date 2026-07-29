"""Repositorio asíncrono Case con ownership y optimistic locking."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import CursorResult

from app.cases.domain import Case, CaseOwnerType, CaseRetentionMode, CaseStatus
from app.database.models.case import CaseAuditEventRecord, CaseRecord
from app.services.conversation_principal import ConversationPrincipal


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _accessible(principal: ConversationPrincipal, now: datetime):
        guest_hash = principal.guest_session_hash if principal.owner_type == "guest" else None
        return select(CaseRecord).where(
            CaseRecord.deleted_at.is_(None),
            or_(
                CaseRecord.owner_type == CaseOwnerType.LOCAL_INSTALLATION.value,
                (
                    (CaseRecord.owner_type == CaseOwnerType.GUEST_SESSION.value)
                    & (CaseRecord.owner_key_hash == guest_hash)
                    & (CaseRecord.expires_at > now)
                ),
            ),
        )

    async def create(self, case: Case, *, event_type: str) -> None:
        self.session.add(self._record(case))
        # No existe una relación ORM deliberadamente: materializa primero el
        # padre para respetar la FK aun con SQLite foreign_keys=ON.
        await self.session.flush()
        self.session.add(self._audit(case, event_type=event_type, from_status=None))
        await self.session.flush()

    async def get_accessible_by_public_id(
        self, public_id: UUID, principal: ConversationPrincipal, *, now: datetime
    ) -> Case | None:
        record = await self.session.scalar(
            self._accessible(principal, now).where(CaseRecord.public_id == public_id)
        )
        return None if record is None else self._domain(record)

    async def get_owned_by_public_id(
        self, public_id: UUID, principal: ConversationPrincipal
    ) -> Case | None:
        guest_hash = principal.guest_session_hash if principal.owner_type == "guest" else None
        record = await self.session.scalar(
            select(CaseRecord).where(
                CaseRecord.public_id == public_id,
                CaseRecord.deleted_at.is_(None),
                or_(
                    CaseRecord.owner_type == CaseOwnerType.LOCAL_INSTALLATION.value,
                    (
                        (CaseRecord.owner_type == CaseOwnerType.GUEST_SESSION.value)
                        & (CaseRecord.owner_key_hash == guest_hash)
                    ),
                ),
            )
        )
        return None if record is None else self._domain(record)

    async def list_accessible_paginated(
        self,
        principal: ConversationPrincipal,
        *,
        now: datetime,
        offset: int,
        limit: int,
    ) -> tuple[list[Case], int]:
        accessible = self._accessible(principal, now)
        total = int(
            (await self.session.scalar(select(func.count()).select_from(accessible.subquery())))
            or 0
        )
        rows = await self.session.scalars(
            accessible.order_by(CaseRecord.updated_at.desc(), CaseRecord.public_id)
            .offset(offset)
            .limit(limit)
        )
        return [self._domain(record) for record in rows.all()], total

    async def update(
        self,
        case: Case,
        *,
        expected_version: int,
        event_type: str,
        from_status: CaseStatus | None,
    ) -> bool:
        result = cast(CursorResult[Any], await self.session.execute(
            update(CaseRecord)
            .where(
                CaseRecord.id == case.id,
                CaseRecord.version == expected_version,
                CaseRecord.deleted_at.is_(None),
            )
            .values(**self._values(case))
        ))
        if result.rowcount != 1:
            return False
        self.session.add(self._audit(case, event_type=event_type, from_status=from_status))
        await self.session.flush()
        return True

    @staticmethod
    def _record(case: Case) -> CaseRecord:
        return CaseRecord(id=case.id, public_id=case.public_id, **CaseRepository._values(case))

    @staticmethod
    def _values(case: Case) -> dict[str, object]:
        return {
            "title": case.title,
            "description": case.description,
            "status": case.status.value,
            "retention_mode": case.retention_mode.value,
            "owner_type": case.owner_type.value,
            "owner_key_hash": case.owner_key_hash,
            "expires_at": case.expires_at,
            "last_activity_at": case.last_activity_at,
            "version": case.version,
            "pre_archive_status": (
                case.pre_archive_status.value if case.pre_archive_status else None
            ),
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "archived_at": case.archived_at,
            "deleted_at": case.deleted_at,
        }

    @staticmethod
    def _domain(record: CaseRecord) -> Case:
        return Case(
            id=record.id,
            public_id=record.public_id,
            title=record.title,
            description=record.description,
            status=CaseStatus(record.status),
            retention_mode=CaseRetentionMode(record.retention_mode),
            owner_type=CaseOwnerType(record.owner_type),
            owner_key_hash=record.owner_key_hash,
            expires_at=record.expires_at,
            last_activity_at=record.last_activity_at,
            version=record.version,
            pre_archive_status=(
                CaseStatus(record.pre_archive_status) if record.pre_archive_status else None
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
            archived_at=record.archived_at,
            deleted_at=record.deleted_at,
        )

    @staticmethod
    def _audit(
        case: Case, *, event_type: str, from_status: CaseStatus | None
    ) -> CaseAuditEventRecord:
        return CaseAuditEventRecord(
            case_id=case.id,
            event_type=event_type,
            actor_type=case.owner_type.value,
            from_status=from_status.value if from_status else None,
            to_status=case.status.value,
            resource_version=case.version,
            result_code="CASE_OPERATION_COMPLETED",
            created_at=case.updated_at,
        )
