"""Esquemas seguros y reutilizables para metadatos documentales."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PureWindowsPath
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    RagEligibilityReason,
    ReviewStatus,
    SourceKind,
)


class DocumentCreate(BaseModel):
    """Metadatos internos requeridos para registrar un documento ya almacenado."""

    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=255)
    display_name: str = Field(default="", max_length=255)
    stored_filename: str = Field(min_length=1, max_length=255)
    relative_path: str = Field(min_length=1, max_length=1024)
    document_type: DocumentType
    mime_type: str = Field(min_length=1, max_length=127)
    extension: str = Field(min_length=1, max_length=16)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    status: DocumentStatus = DocumentStatus.REGISTERED
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    source_kind: SourceKind = SourceKind.LOCAL_UPLOAD
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    legal_validity_status: LegalValidityStatus = LegalValidityStatus.UNKNOWN
    index_status: IndexStatus = IndexStatus.NOT_REQUESTED
    issuing_entity: str | None = Field(default=None, max_length=255)
    jurisdiction: str | None = Field(default=None, max_length=120)
    legal_area: str | None = Field(default=None, max_length=120)
    canonical_source_url: str | None = Field(default=None, max_length=2048)
    published_at: datetime | None = None
    source_accessed_at: datetime | None = None
    version_label: str | None = Field(default=None, max_length=120)
    expires_at: datetime | None = None
    archived_at: datetime | None = None
    archive_reason: str | None = Field(default=None, max_length=500)
    rejection_reason: str | None = Field(default=None, max_length=500)
    supersedes_document_id: UUID | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=500)

    @field_validator("sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        """Acepta únicamente hashes SHA-256 hexadecimales completos."""

        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("sha256 debe contener 64 caracteres hexadecimales")
        return normalized

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        """Evita rutas absolutas y navegación ascendente en metadatos."""

        normalized = value.replace("\\", "/")
        windows_path = PureWindowsPath(value)
        if (
            Path(normalized).is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in Path(normalized).parts
            or not normalized.startswith("storage/documents/")
        ):
            raise ValueError(
                "relative_path debe ser una ruta relativa segura dentro de storage/documents"
            )
        return normalized

    @field_validator(
        "issuing_entity",
        "jurisdiction",
        "legal_area",
        "canonical_source_url",
        "version_label",
        "archive_reason",
        "rejection_reason",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "published_at",
        "source_accessed_at",
        "expires_at",
        "archived_at",
    )
    @classmethod
    def require_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Las fechas documentales deben incluir zona horaria")
        return value

    @model_validator(mode="after")
    def validate_governance(self) -> "DocumentCreate":
        self.display_name = self.display_name.strip() or self.original_filename
        if (
            self.published_at is not None
            and self.source_accessed_at is not None
            and self.source_accessed_at < self.published_at
        ):
            raise ValueError("source_accessed_at no puede preceder published_at")
        return self


class DocumentUploadGovernance(BaseModel):
    """Gobernanza permitida en la carga pública ordinaria."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    source_kind: SourceKind = SourceKind.LOCAL_UPLOAD
    expires_at: datetime | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name no puede estar vacío")
        return normalized

    @field_validator("expires_at")
    @classmethod
    def validate_expiration_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("expires_at debe incluir zona horaria")
        return value

class DocumentRead(BaseModel):
    """Contrato público sin metadatos privados de almacenamiento."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    original_filename: str
    document_type: DocumentType
    mime_type: str
    extension: str
    size_bytes: int
    status: DocumentStatus
    knowledge_layer: KnowledgeLayer
    source_kind: SourceKind
    review_status: ReviewStatus
    legal_validity_status: LegalValidityStatus
    index_status: IndexStatus
    issuing_entity: str | None
    jurisdiction: str | None
    legal_area: str | None
    canonical_source_url: str | None
    published_at: datetime | None
    source_accessed_at: datetime | None
    version_label: str | None
    expires_at: datetime | None
    archived_at: datetime | None
    supersedes_document_id: UUID | None
    created_at: datetime
    updated_at: datetime
    rag_eligible: bool
    rag_eligibility_reasons: list[RagEligibilityReason]
    is_expired: bool


class DocumentStatusRead(BaseModel):
    """Estado documental reutilizable para flujos internos futuros."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: DocumentStatus
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class DocumentListFilters(BaseModel):
    """Filtros de repositorio; la API los reutilizará en un bloque posterior."""

    model_config = ConfigDict(extra="forbid")

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    document_type: DocumentType | None = None
    status: DocumentStatus | None = None
    include_deleted: bool = False


class DocumentPage(BaseModel):
    """Resultado paginado de metadatos seguros."""

    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class ExtractedPageRead(BaseModel):
    """Página extraída sin exponer metadatos de almacenamiento."""

    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    char_count: int


class ExtractedChunkRead(BaseModel):
    """Chunk jurídico trazable sin semántica adicional."""

    model_config = ConfigDict(from_attributes=True)

    chunk_index: int
    text: str
    char_count: int
    word_count: int
    start_page: int
    end_page: int


class ExtractedPagesPage(BaseModel):
    items: list[ExtractedPageRead]
    total: int
    page: int
    page_size: int


class ExtractedChunksPage(BaseModel):
    items: list[ExtractedChunkRead]
    total: int
    page: int
    page_size: int


class ExtractionSummary(BaseModel):
    document_id: UUID
    status: DocumentStatus
    total_pages: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_characters: int = Field(ge=0)
