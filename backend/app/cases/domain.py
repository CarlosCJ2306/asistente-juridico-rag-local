"""Dominio Case independiente de SQLAlchemy, FastAPI y esquemas HTTP."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from types import MappingProxyType
from uuid import UUID, uuid4


CASE_TITLE_MAX_LENGTH = 200
CASE_DESCRIPTION_MAX_LENGTH = 2000


class CaseStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    IN_REVIEW = "in_review"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CaseRetentionMode(str, Enum):
    TEMPORARY = "temporary"
    LOCAL_PERSISTENT = "local_persistent"


class CaseOwnerType(str, Enum):
    GUEST_SESSION = "guest_session"
    LOCAL_INSTALLATION = "local_installation"
    ACCOUNT = "account"


CASE_TRANSITIONS = MappingProxyType(
    {
        CaseStatus.DRAFT: frozenset({CaseStatus.ACTIVE, CaseStatus.ARCHIVED}),
        CaseStatus.ACTIVE: frozenset(
            {CaseStatus.IN_REVIEW, CaseStatus.CLOSED, CaseStatus.ARCHIVED}
        ),
        CaseStatus.IN_REVIEW: frozenset(
            {CaseStatus.ACTIVE, CaseStatus.CLOSED, CaseStatus.ARCHIVED}
        ),
        CaseStatus.CLOSED: frozenset({CaseStatus.ACTIVE, CaseStatus.ARCHIVED}),
        CaseStatus.ARCHIVED: frozenset(),
    }
)


class CaseDomainError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Case:
    id: UUID
    public_id: UUID
    title: str
    description: str | None
    status: CaseStatus
    retention_mode: CaseRetentionMode
    owner_type: CaseOwnerType
    owner_key_hash: str | None
    expires_at: datetime | None
    last_activity_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime
    pre_archive_status: CaseStatus | None = None
    archived_at: datetime | None = None
    deleted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        title: str,
        description: str | None,
        retention_mode: CaseRetentionMode,
        owner_key_hash: str | None,
        now: datetime,
        retention_days: int,
    ) -> "Case":
        if retention_mode is CaseRetentionMode.TEMPORARY:
            if owner_key_hash is None or len(owner_key_hash) != 64:
                raise CaseDomainError("CASE_RETENTION_INVALID")
            owner_type = CaseOwnerType.GUEST_SESSION
            expires_at = now + timedelta(days=retention_days)
        else:
            if owner_key_hash is not None:
                raise CaseDomainError("CASE_RETENTION_INVALID")
            owner_type = CaseOwnerType.LOCAL_INSTALLATION
            expires_at = None
        return cls(
            id=uuid4(),
            public_id=uuid4(),
            title=normalize_case_title(title),
            description=normalize_case_description(description),
            status=CaseStatus.DRAFT,
            retention_mode=retention_mode,
            owner_type=owner_type,
            owner_key_hash=owner_key_hash,
            expires_at=expires_at,
            last_activity_at=now,
            version=1,
            created_at=now,
            updated_at=now,
        )

    @property
    def read_only(self) -> bool:
        return self.status is CaseStatus.ARCHIVED

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now

    def touch(self, *, now: datetime, retention_days: int) -> "Case":
        expiry = (
            now + timedelta(days=retention_days)
            if self.retention_mode is CaseRetentionMode.TEMPORARY
            else None
        )
        return replace(
            self,
            expires_at=expiry,
            last_activity_at=now,
            updated_at=now,
            version=self.version + 1,
        )

    def update_content(
        self,
        *,
        title: str | None,
        description: str | None,
        description_supplied: bool,
        now: datetime,
        retention_days: int,
    ) -> "Case":
        if self.read_only:
            raise CaseDomainError("CASE_ARCHIVED_READ_ONLY")
        touched = self.touch(now=now, retention_days=retention_days)
        return replace(
            touched,
            title=self.title if title is None else normalize_case_title(title),
            description=(
                self.description
                if not description_supplied
                else normalize_case_description(description)
            ),
        )

    def transition(
        self, *, target: CaseStatus, now: datetime, retention_days: int
    ) -> "Case":
        if target not in CASE_TRANSITIONS[self.status]:
            raise CaseDomainError("CASE_INVALID_TRANSITION")
        touched = self.touch(now=now, retention_days=retention_days)
        if target is CaseStatus.ARCHIVED:
            return replace(
                touched,
                status=target,
                pre_archive_status=self.status,
                archived_at=now,
            )
        return replace(touched, status=target)

    def restore(self, *, now: datetime, retention_days: int) -> "Case":
        if self.status is not CaseStatus.ARCHIVED:
            raise CaseDomainError("CASE_INVALID_TRANSITION")
        target = self.pre_archive_status or CaseStatus.DRAFT
        if target is CaseStatus.ARCHIVED:
            target = CaseStatus.DRAFT
        touched = self.touch(now=now, retention_days=retention_days)
        return replace(
            touched,
            status=target,
            pre_archive_status=None,
            archived_at=None,
        )

    def soft_delete(self, *, now: datetime) -> "Case":
        return replace(
            self,
            deleted_at=now,
            updated_at=now,
            last_activity_at=now,
            version=self.version + 1,
        )


def _normalize(value: str, *, code: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    if (
        not normalized
        or len(normalized) > maximum
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise CaseDomainError(code)
    return normalized


def normalize_case_title(value: str) -> str:
    return _normalize(value, code="CASE_TITLE_INVALID", maximum=CASE_TITLE_MAX_LENGTH)


def normalize_case_description(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize(
        value,
        code="CASE_DESCRIPTION_INVALID",
        maximum=CASE_DESCRIPTION_MAX_LENGTH,
    )
