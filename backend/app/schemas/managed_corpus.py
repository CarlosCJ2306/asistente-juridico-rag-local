"""Contratos internos y seguros del corpus jurídico administrado."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.database.models.document import (
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    ReviewStatus,
)


class ManagedCorpusManifestDocument(BaseModel):
    """Metadatos versionables; nunca contiene rutas internas ni estados finales."""

    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    filename: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=255)
    document_type: DocumentType
    issuing_entity: str | None = Field(default=None, max_length=255)
    jurisdiction: str | None = Field(default=None, max_length=120)
    legal_area: str | None = Field(default=None, max_length=120)
    canonical_source_url: str | None = Field(default=None, max_length=2048)
    published_at: datetime | None = None
    version_label: str | None = Field(default=None, max_length=120)
    supersedes_source_key: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    administrative_note: str | None = Field(default=None, max_length=500)

    @field_validator(
        "display_name",
        "issuing_entity",
        "jurisdiction",
        "legal_area",
        "version_label",
        "administrative_note",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(character) < 32 for character in value):
            raise ValueError("MANAGED_CORPUS_TEXT_INVALID")
        normalized = value.strip()
        return normalized or None

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        windows_path = PureWindowsPath(value)
        if (
            path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in path.parts
            or not path.parts
            or path.suffix.lower() != ".pdf"
            or any(part in {"", "."} for part in path.parts)
        ):
            raise ValueError("MANAGED_CORPUS_FILENAME_INVALID")
        return path.as_posix()

    @field_validator("expected_sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("MANAGED_CORPUS_SHA256_INVALID")
        return normalized

    @field_validator("canonical_source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("MANAGED_CORPUS_URL_INVALID")
        return value.strip()

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("MANAGED_CORPUS_DATE_INVALID")
        return value

    @model_validator(mode="after")
    def validate_version_link(self) -> "ManagedCorpusManifestDocument":
        if self.supersedes_source_key == self.source_key:
            raise ValueError("MANAGED_CORPUS_VERSION_SELF_REFERENCE")
        return self


class ManagedCorpusManifest(BaseModel):
    """Manifiesto completo con claves deterministas y únicas."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    corpus_id: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    documents: list[ManagedCorpusManifestDocument] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_manifest(self) -> "ManagedCorpusManifest":
        if self.schema_version != 1:
            raise ValueError("MANAGED_CORPUS_SCHEMA_UNSUPPORTED")
        source_keys = [item.source_key for item in self.documents]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("MANAGED_CORPUS_SOURCE_KEY_DUPLICATE")
        filenames = [item.filename.casefold() for item in self.documents]
        if len(filenames) != len(set(filenames)):
            raise ValueError("MANAGED_CORPUS_FILENAME_DUPLICATE")
        preceding_sources: set[str] = set()
        for item in self.documents:
            if (
                item.supersedes_source_key is not None
                and item.supersedes_source_key not in preceding_sources
            ):
                raise ValueError("MANAGED_CORPUS_PREVIOUS_VERSION_ORDER_INVALID")
            preceding_sources.add(item.source_key)
        return self


class ManagedCorpusOperation(str, Enum):
    VALIDATE = "validate"
    IMPORT = "import"
    STATUS = "status"
    REVIEW = "review"
    PROMOTE = "promote"


class ManagedCorpusItemStatus(str, Enum):
    VALID = "valid"
    NOT_IMPORTED = "not_imported"
    IMPORTED_PENDING = "imported_pending"
    APPROVED = "approved"
    PROCESSED = "processed"
    INDEXED = "indexed"
    REJECTED = "rejected"
    CONFLICT = "conflict"
    INVALID = "invalid"
    ERROR = "error"


class ManagedCorpusResult(BaseModel):
    """Salida sanitizada compartida por servicio y CLI."""

    source_key: str
    operation: ManagedCorpusOperation
    status: ManagedCorpusItemStatus
    safe_reason_code: str | None = None
    document_id: str | None = None
    knowledge_layer: KnowledgeLayer | None = None
    review_status: ReviewStatus | None = None
    legal_validity_status: LegalValidityStatus | None = None
    index_status: IndexStatus | None = None


class ManagedCorpusBatchResult(BaseModel):
    corpus_id: str
    operation: ManagedCorpusOperation
    results: list[ManagedCorpusResult]
    succeeded: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    failed: int = Field(ge=0)
