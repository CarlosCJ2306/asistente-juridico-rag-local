"""Persistencia del núcleo Case y su auditoría estructurada."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import UTCDateTime, utc_now


class CaseRecord(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("status IN ('draft','active','in_review','closed','archived')", name="ck_cases_status"),
        CheckConstraint("retention_mode IN ('temporary','local_persistent')", name="ck_cases_retention_mode"),
        CheckConstraint("owner_type IN ('guest_session','local_installation','account')", name="ck_cases_owner_type"),
        CheckConstraint(
            "(retention_mode='temporary' AND owner_type='guest_session' AND owner_key_hash IS NOT NULL AND expires_at IS NOT NULL) OR "
            "(retention_mode='local_persistent' AND owner_type='local_installation' AND owner_key_hash IS NULL AND expires_at IS NULL)",
            name="ck_cases_retention_owner",
        ),
        CheckConstraint("version >= 1", name="ck_cases_version"),
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="ck_cases_title"),
        Index("ix_cases_owner_access", "owner_type", "owner_key_hash", "deleted_at"),
        Index("ix_cases_status", "status"),
        Index("ix_cases_retention_mode", "retention_mode"),
        Index("ix_cases_expires_at", "expires_at"),
        Index("ix_cases_deleted_at", "deleted_at"),
        Index("ix_cases_updated_at", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    retention_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(24), nullable=False)
    owner_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pre_archive_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class CaseAuditEventRecord(Base):
    __tablename__ = "case_audit_events"
    __table_args__ = (
        CheckConstraint("resource_version >= 1", name="ck_case_audit_version"),
        Index("ix_case_audit_case_created", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
