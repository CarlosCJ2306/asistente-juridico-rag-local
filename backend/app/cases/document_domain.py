"""Dominio CaseDocument independiente de ORM, HTTP y servicios documentales."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


CASE_DOCUMENT_MAX_ORDER = 1_000_000


class CaseDocumentPurpose(str, Enum):
    PRIMARY_RECORD = "primary_record"
    ANNEX = "annex"
    EVIDENCE = "evidence"
    OTHER = "other"


class CaseDocumentAvailability(str, Enum):
    AVAILABLE = "available"
    PENDING_PROCESSING = "pending_processing"
    STALE = "stale"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


class CaseDocumentWarning(str, Enum):
    SNAPSHOT_CHANGED = "snapshot_changed"
    PROCESSING_PENDING = "processing_pending"
    DOCUMENT_EXPIRED = "document_expired"
    DOCUMENT_UNAVAILABLE = "document_unavailable"
    LAYER_NOT_ALLOWED = "layer_not_allowed"
    RAG_INELIGIBLE = "rag_ineligible"


class CaseDocumentDomainError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CaseDocumentSnapshot:
    display_name: str
    document_type: str
    knowledge_layer: str
    source_kind: str
    review_status: str
    legal_validity_status: str
    extraction_status: str
    index_status: str
    expires_at: datetime | None
    document_updated_at: datetime
    document_version_label: str | None


@dataclass(frozen=True, slots=True)
class CaseDocument:
    id: UUID
    public_id: UUID
    case_id: UUID
    document_id: UUID
    purpose: CaseDocumentPurpose
    display_order: int
    snapshot: CaseDocumentSnapshot
    version: int
    attached_at: datetime
    updated_at: datetime
    removed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        case_id: UUID,
        document_id: UUID,
        purpose: CaseDocumentPurpose,
        display_order: int,
        snapshot: CaseDocumentSnapshot,
        now: datetime,
    ) -> "CaseDocument":
        validate_display_order(display_order)
        return cls(
            id=uuid4(),
            public_id=uuid4(),
            case_id=case_id,
            document_id=document_id,
            purpose=purpose,
            display_order=display_order,
            snapshot=snapshot,
            version=1,
            attached_at=now,
            updated_at=now,
        )

    def update_link(
        self,
        *,
        purpose: CaseDocumentPurpose | None,
        display_order: int | None,
        now: datetime,
    ) -> "CaseDocument":
        if self.removed_at is not None:
            raise CaseDocumentDomainError("CASE_DOCUMENT_NOT_FOUND")
        effective_order = self.display_order if display_order is None else display_order
        validate_display_order(effective_order)
        return replace(
            self,
            purpose=self.purpose if purpose is None else purpose,
            display_order=effective_order,
            version=self.version + 1,
            updated_at=now,
        )

    def remove(self, *, now: datetime) -> "CaseDocument":
        if self.removed_at is not None:
            raise CaseDocumentDomainError("CASE_DOCUMENT_NOT_FOUND")
        return replace(
            self,
            version=self.version + 1,
            updated_at=now,
            removed_at=now,
        )


def validate_display_order(value: int) -> None:
    if isinstance(value, bool) or not 0 <= value <= CASE_DOCUMENT_MAX_ORDER:
        raise CaseDocumentDomainError("CASE_DOCUMENT_INVALID_ORDER")
