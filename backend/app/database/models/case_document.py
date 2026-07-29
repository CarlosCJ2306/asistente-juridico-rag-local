"""Asociación persistente entre Case y Document, sin contenido documental."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import UTCDateTime, utc_now


class CaseDocumentRecord(Base):
    __tablename__ = "case_documents"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('primary_record','annex','evidence','other')",
            name="ck_case_documents_purpose",
        ),
        CheckConstraint(
            "display_order BETWEEN 0 AND 1000000",
            name="ck_case_documents_display_order",
        ),
        CheckConstraint("version >= 1", name="ck_case_documents_version"),
        CheckConstraint(
            "updated_at >= attached_at AND (removed_at IS NULL OR removed_at >= attached_at)",
            name="ck_case_documents_timestamps",
        ),
        Index("ix_case_documents_case_id", "case_id"),
        Index("ix_case_documents_document_id", "document_id"),
        Index("ix_case_documents_case_order", "case_id", "display_order"),
        Index("ix_case_documents_case_removed", "case_id", "removed_at"),
        Index("ix_case_documents_attached_at", "attached_at"),
        Index(
            "uq_case_documents_active_case_document",
            "case_id",
            "document_id",
            unique=True,
            sqlite_where=text("removed_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_knowledge_layer: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_legal_validity_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_index_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    snapshot_document_updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False
    )
    snapshot_document_version_label: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attached_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
