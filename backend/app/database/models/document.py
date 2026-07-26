"""Metadatos persistentes de documentos, sin contenido ni operaciones de archivo."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base


def utc_now() -> datetime:
    """Genera una fecha consciente de zona horaria en UTC."""

    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Conserva UTC explícito al guardar fechas en SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Any,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Los timestamps de documentos deben incluir zona horaria")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Any,
    ) -> datetime | None:
        del dialect
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class DocumentType(str, Enum):
    """Clasificación inicial de metadatos documentales."""

    EXPEDIENTE = "expediente"
    NORMATIVA = "normativa"
    JURISPRUDENCIA = "jurisprudencia"
    OTRO = "otro"


class DocumentStatus(str, Enum):
    """Estados iniciales del ciclo documental, sin extracción en este bloque."""

    REGISTERED = "registered"
    STORED = "stored"
    PENDING_EXTRACTION = "pending_extraction"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    EXTRACTION_FAILED = "extraction_failed"
    FAILED = "failed"
    ARCHIVED = "archived"


class KnowledgeLayer(str, Enum):
    """Capa de conocimiento asignada al documento."""

    MANAGED_CORPUS = "managed_corpus"
    PRIVATE_LIBRARY = "private_library"
    TEMPORARY = "temporary"
    WEB_VERIFIED = "web_verified"
    GLOBAL_CANDIDATE = "global_candidate"


class SourceKind(str, Enum):
    """Procedencia técnica controlada del documento."""

    LOCAL_UPLOAD = "local_upload"
    MANAGED_IMPORT = "managed_import"
    WEB_IMPORT = "web_import"


class ReviewStatus(str, Enum):
    """Estado editorial independiente del procesamiento técnico."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class LegalValidityStatus(str, Enum):
    """Vigencia jurídica declarada, sin inferencia automática."""

    UNKNOWN = "unknown"
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REPEALED = "repealed"
    EXPIRED = "expired"


class IndexStatus(str, Enum):
    """Estado operativo de indexación derivada."""

    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    EXCLUDED = "excluded"


def enum_values(enum_class: type[Enum]) -> list[str]:
    """Persiste valores legibles de enums en lugar de sus nombres Python."""

    return [member.value for member in enum_class]


class Document(Base):
    """Registro de metadatos y estado; nunca almacena contenido documental."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "supersedes_document_id IS NULL OR supersedes_document_id <> id",
            name="ck_documents_supersedes_not_self",
        ),
        Index("ix_documents_knowledge_layer_deleted", "knowledge_layer", "is_deleted"),
        Index("ix_documents_review_status", "review_status"),
        Index("ix_documents_legal_validity_status", "legal_validity_status"),
        Index("ix_documents_index_status", "index_status"),
        Index("ix_documents_expires_at", "expires_at"),
        Index("ix_documents_supersedes_document_id", "supersedes_document_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Documento"
    )
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    document_type: Mapped[DocumentType] = mapped_column(
        SqlEnum(
            DocumentType,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(
            DocumentStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=DocumentStatus.REGISTERED,
        index=True,
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
        default=KnowledgeLayer.PRIVATE_LIBRARY,
    )
    source_kind: Mapped[SourceKind] = mapped_column(
        SqlEnum(
            SourceKind,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=SourceKind.LOCAL_UPLOAD,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        SqlEnum(
            ReviewStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=ReviewStatus.NOT_REQUIRED,
    )
    legal_validity_status: Mapped[LegalValidityStatus] = mapped_column(
        SqlEnum(
            LegalValidityStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=LegalValidityStatus.UNKNOWN,
    )
    index_status: Mapped[IndexStatus] = mapped_column(
        SqlEnum(
            IndexStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
        default=IndexStatus.NOT_REQUESTED,
    )
    issuing_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(120), nullable=True)
    legal_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    canonical_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source_accessed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    version_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supersedes_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
