"""Esquemas seguros y reutilizables para metadatos documentales."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PureWindowsPath
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database.models.document import DocumentStatus, DocumentType


class DocumentCreate(BaseModel):
    """Metadatos internos requeridos para registrar un documento ya almacenado."""

    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=255)
    stored_filename: str = Field(min_length=1, max_length=255)
    relative_path: str = Field(min_length=1, max_length=1024)
    document_type: DocumentType
    mime_type: str = Field(min_length=1, max_length=127)
    extension: str = Field(min_length=1, max_length=16)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    status: DocumentStatus = DocumentStatus.REGISTERED
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


class DocumentRead(BaseModel):
    """Lectura segura sin rutas absolutas ni mensajes internos de error."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    stored_filename: str
    relative_path: str
    document_type: DocumentType
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    is_deleted: bool


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
