"""Cola persistente y sanitizada del procesamiento documental local."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum as SqlEnum, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import KnowledgeLayer, UTCDateTime, enum_values, utc_now


class DocumentProcessingState(str, Enum):
    QUEUED = "queued"
    DETECTING = "detecting"
    REGISTERING = "registering"
    EXTRACTING = "extracting"
    WAITING_FOR_INDEX = "waiting_for_index"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class DocumentProcessingOperation(str, Enum):
    INBOX_IMPORT = "inbox_import"
    UPLOAD_PIPELINE = "upload_pipeline"


ACTIVE_PROCESSING_STATES = (
    DocumentProcessingState.QUEUED,
    DocumentProcessingState.DETECTING,
    DocumentProcessingState.REGISTERING,
    DocumentProcessingState.EXTRACTING,
    DocumentProcessingState.WAITING_FOR_INDEX,
    DocumentProcessingState.INDEXING,
)


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_document_processing_jobs_attempts"),
        Index("ix_document_processing_jobs_state_created", "state", "created_at"),
        Index("ix_document_processing_jobs_document_id", "document_id"),
        Index(
            "uq_document_processing_jobs_active_inbox_path",
            "inbox_relative_path",
            unique=True,
            sqlite_where=text(
                "inbox_relative_path IS NOT NULL AND state IN "
                "('queued','detecting','registering','extracting','waiting_for_index','indexing')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    knowledge_layer: Mapped[KnowledgeLayer] = mapped_column(
        SqlEnum(
            KnowledgeLayer,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )
    public_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[DocumentProcessingOperation] = mapped_column(
        SqlEnum(
            DocumentProcessingOperation,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )
    state: Mapped[DocumentProcessingState] = mapped_column(
        SqlEnum(
            DocumentProcessingState,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=DocumentProcessingState.QUEUED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inbox_relative_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
