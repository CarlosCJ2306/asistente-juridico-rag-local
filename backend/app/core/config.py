"""Configuración centralizada obtenida del entorno y del archivo raíz `.env`."""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import (
    DATABASE_DIR,
    LOGS_DIR,
    PROJECT_ROOT,
    resolve_database_file,
    resolve_embedding_model_directory,
)


class Settings(BaseSettings):
    """Opciones de ejecución del backend."""

    app_name: str = "Asistente Jurídico RAG Local"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api"
    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    log_level: str = "INFO"
    log_to_file: bool = True
    log_console: bool = True
    log_dir: Path = LOGS_DIR
    log_file_name: str = "asistente_juridico_backend.log"
    log_max_bytes: int = 5_242_880
    log_backup_count: int = 5

    database_file: Path = DATABASE_DIR / "asistente_juridico.db"

    document_max_size_bytes: int = Field(default=52_428_800, gt=0)
    document_upload_chunk_size_bytes: int = Field(default=1_048_576, gt=0)
    legal_chunk_target_chars: int = Field(default=1800, gt=0)
    legal_chunk_max_chars: int = Field(default=2400, gt=0)
    legal_chunk_overlap_chars: int = Field(default=200, ge=0)
    pdf_min_extractable_chars: int = Field(default=20, gt=0)

    local_llm_context_size: int = 4096
    local_llm_threads: int = 0
    local_llm_gpu_layers: int = 0
    local_llm_verbose: bool = False

    embedding_model_path: Path = Field(
        default=Path("models/embeddings/multilingual-e5-small"),
        validate_default=True,
    )
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cpu"
    embedding_batch_size: int = Field(default=16, gt=0)
    embedding_normalize: bool = True
    embedding_query_prefix: str = "query:"
    embedding_passage_prefix: str = "passage:"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_value(cls, value: Any) -> Any:
        """Tolera etiquetas comunes de entorno que colisionan con DEBUG."""

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    @field_validator("database_file", mode="before")
    @classmethod
    def resolve_database_path(cls, value: str | Path) -> Path:
        """Acepta solo rutas de SQLite contenidas en el directorio autorizado."""

        return resolve_database_file(value)

    @field_validator("embedding_model_path", mode="before")
    @classmethod
    def resolve_embedding_model_path(cls, value: str | Path) -> Path:
        return resolve_embedding_model_directory(value)

    @field_validator("embedding_query_prefix", "embedding_passage_prefix")
    @classmethod
    def validate_embedding_prefix(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Los prefijos de embeddings no pueden estar vacíos")
        return value

    @model_validator(mode="after")
    def validate_document_limits(self) -> "Settings":
        """Valida límites consistentes de carga y segmentación documental."""

        if self.document_upload_chunk_size_bytes > self.document_max_size_bytes:
            raise ValueError(
                "DOCUMENT_UPLOAD_CHUNK_SIZE_BYTES no puede superar DOCUMENT_MAX_SIZE_BYTES"
            )
        if self.legal_chunk_target_chars > self.legal_chunk_max_chars:
            raise ValueError("LEGAL_CHUNK_TARGET_CHARS no puede superar LEGAL_CHUNK_MAX_CHARS")
        if self.legal_chunk_overlap_chars >= self.legal_chunk_target_chars:
            raise ValueError("LEGAL_CHUNK_OVERLAP_CHARS debe ser menor que LEGAL_CHUNK_TARGET_CHARS")
        return self

    @property
    def log_file_path(self) -> Path:
        """Devuelve la ruta absoluta del archivo de log."""

        directory = self.log_dir
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory
        return (directory / self.log_file_name).resolve()


settings = Settings()
