"""Configuración centralizada obtenida del entorno y del archivo raíz `.env`."""

import math
import re
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
    resolve_inbox_directory,
    resolve_managed_corpus_staging_directory,
    resolve_vector_path,
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
    managed_corpus_staging_path: Path = Field(
        default=Path("storage/staging/managed_corpus"),
        validate_default=True,
    )

    document_max_size_bytes: int = Field(default=52_428_800, gt=0)
    document_upload_chunk_size_bytes: int = Field(default=1_048_576, gt=0)
    legal_chunk_target_chars: int = Field(default=1800, gt=0)
    legal_chunk_max_chars: int = Field(default=2400, gt=0)
    legal_chunk_overlap_chars: int = Field(default=200, ge=0)
    pdf_min_extractable_chars: int = Field(default=20, gt=0)
    document_automation_enabled: bool = True
    document_inbox_scan_interval_seconds: float = Field(default=5.0, ge=1.0, le=3600)
    document_inbox_stability_seconds: float = Field(default=2.0, ge=0.5, le=300)
    document_inbox_unstable_timeout_seconds: float = Field(
        default=900.0, ge=30, le=86400
    )
    document_inbox_max_files_per_scan: int = Field(default=100, ge=1, le=10000)
    document_sidecar_max_bytes: int = Field(default=16384, ge=256, le=1048576)
    document_processing_max_retries: int = Field(default=3, ge=1, le=10)
    document_processing_recent_limit: int = Field(default=20, ge=1, le=100)
    document_index_debounce_seconds: float = Field(default=2.0, ge=0, le=60)
    document_inbox_private_path: Path = Field(
        default=Path("storage/inbox/private_library"), validate_default=True
    )
    document_inbox_temporary_path: Path = Field(
        default=Path("storage/inbox/temporary"), validate_default=True
    )
    document_inbox_processed_path: Path = Field(
        default=Path("storage/inbox/processed"), validate_default=True
    )
    document_inbox_quarantine_path: Path = Field(
        default=Path("storage/inbox/quarantine"), validate_default=True
    )

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
    embedding_runtime_policy: str = "on_demand"
    embedding_idle_unload_seconds: float = Field(default=120.0, ge=5, le=86400)
    embedding_query_prefix: str = "query:"
    embedding_passage_prefix: str = "passage:"

    text_search_query_max_chars: int = Field(default=500, gt=0)
    text_search_max_terms: int = Field(default=32, gt=0)
    text_search_default_page_size: int = Field(default=20, gt=0)
    text_search_max_page_size: int = Field(default=100, gt=0)
    text_search_max_document_types: int = Field(default=10, gt=0)

    chroma_persist_path: Path = Field(
        default=Path("storage/vector/chroma"), validate_default=True
    )
    semantic_index_state_file: Path = Field(
        default=Path("storage/vector/semantic_index_state.json"),
        validate_default=True,
    )
    semantic_collection_prefix: str = "legal_chunks"
    semantic_index_schema_version: int = Field(default=2, gt=0)
    semantic_index_batch_size: int = Field(default=32, gt=0)
    semantic_search_top_k_default: int = Field(default=10, gt=0)
    semantic_search_top_k_max: int = Field(default=50, gt=0)
    semantic_search_candidate_multiplier: int = Field(default=3, ge=1, le=10)
    semantic_snippet_max_length: int = Field(default=500, gt=0, le=5000)
    semantic_query_max_chars: int = Field(default=1000, gt=0)
    semantic_max_document_types: int = Field(default=10, gt=0)

    hybrid_rrf_k: int = Field(default=60, gt=0, le=1000)
    hybrid_text_weight: float = Field(default=1.0, gt=0, le=10.0)
    hybrid_semantic_weight: float = Field(default=1.0, gt=0, le=10.0)
    hybrid_top_k_default: int = Field(default=10, gt=0)
    hybrid_top_k_max: int = Field(default=50, gt=0)
    hybrid_candidate_multiplier: int = Field(default=3, ge=1, le=10)

    rag_top_k_default: int = Field(default=8, gt=0)
    rag_top_k_max: int = Field(default=20, gt=0, le=50)
    rag_context_max_chunks: int = Field(default=8, gt=0)
    rag_context_max_tokens: int = Field(default=2200, gt=0)
    rag_max_new_tokens: int = Field(default=512, gt=0)
    rag_token_safety_margin: int = Field(default=128, gt=0)
    rag_question_max_length: int = Field(default=2000, gt=0, le=10000)
    rag_answer_max_length: int = Field(default=6000, gt=0, le=20000)
    rag_temperature: float = Field(default=0.1, ge=0, le=2)
    rag_top_p: float = Field(default=0.9, gt=0, le=1)
    rag_repeat_penalty: float = Field(default=1.05, gt=0, le=2)
    rag_citation_max_sources: int = Field(default=8, gt=0)
    rag_source_name_max_length: int = Field(default=255, gt=0, le=500)

    hpn_matrix_title_max_length: int = Field(default=200, gt=0, le=200)
    hpn_matrix_description_max_length: int = Field(default=4000, gt=0, le=20000)
    hpn_node_title_max_length: int = Field(default=200, gt=0, le=200)
    hpn_node_statement_max_length: int = Field(default=8000, gt=0, le=50000)
    hpn_relation_rationale_max_length: int = Field(default=4000, gt=0, le=20000)
    hpn_max_nodes_per_matrix: int = Field(default=500, gt=0, le=5000)
    hpn_max_relations_per_matrix: int = Field(default=2000, gt=0, le=20000)
    hpn_max_sources_per_node: int = Field(default=20, gt=0, le=100)
    hpn_source_name_max_length: int = Field(default=255, gt=0, le=255)

    graph_max_nodes: int = Field(default=300, gt=0, le=5000)
    graph_max_edges: int = Field(default=1000, gt=0, le=20000)
    graph_max_label_length: int = Field(default=80, gt=0, le=200)
    graph_max_components_detail: int = Field(default=100, gt=0, le=5000)
    graph_max_html_bytes: int = Field(default=5_242_880, gt=0, le=20_971_520)
    graph_max_tooltip_length: int = Field(default=240, gt=0, le=1000)
    graph_render_concurrency: int = Field(default=1, gt=0, le=8)

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

    @field_validator("managed_corpus_staging_path", mode="before")
    @classmethod
    def resolve_managed_staging_path(cls, value: str | Path) -> Path:
        return resolve_managed_corpus_staging_directory(value)

    @field_validator("document_inbox_private_path", mode="before")
    @classmethod
    def resolve_private_inbox_path(cls, value: str | Path) -> Path:
        return resolve_inbox_directory(value, expected_name="private_library")

    @field_validator("document_inbox_temporary_path", mode="before")
    @classmethod
    def resolve_temporary_inbox_path(cls, value: str | Path) -> Path:
        return resolve_inbox_directory(value, expected_name="temporary")

    @field_validator("document_inbox_processed_path", mode="before")
    @classmethod
    def resolve_processed_inbox_path(cls, value: str | Path) -> Path:
        return resolve_inbox_directory(value, expected_name="processed")

    @field_validator("document_inbox_quarantine_path", mode="before")
    @classmethod
    def resolve_quarantine_inbox_path(cls, value: str | Path) -> Path:
        return resolve_inbox_directory(value, expected_name="quarantine")

    @field_validator("embedding_model_path", mode="before")
    @classmethod
    def resolve_embedding_model_path(cls, value: str | Path) -> Path:
        return resolve_embedding_model_directory(value)

    @field_validator("chroma_persist_path", mode="before")
    @classmethod
    def resolve_chroma_path(cls, value: str | Path) -> Path:
        return resolve_vector_path(value, expected_directory=True)

    @field_validator("semantic_index_state_file", mode="before")
    @classmethod
    def resolve_semantic_state_path(cls, value: str | Path) -> Path:
        resolved = resolve_vector_path(value, expected_directory=False)
        if resolved.suffix.lower() != ".json":
            raise ValueError("VECTOR_STORE_PATH_INVALID")
        return resolved

    @field_validator("semantic_collection_prefix")
    @classmethod
    def validate_collection_prefix(cls, value: str) -> str:
        normalized = value.strip()
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,48}", normalized) is None:
            raise ValueError("SEMANTIC_COLLECTION_PREFIX_INVALID")
        return normalized

    @field_validator("embedding_query_prefix", "embedding_passage_prefix")
    @classmethod
    def validate_embedding_prefix(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Los prefijos de embeddings no pueden estar vacíos")
        return value

    @field_validator("embedding_runtime_policy")
    @classmethod
    def validate_embedding_runtime_policy(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"manual", "on_demand"}:
            raise ValueError("EMBEDDING_RUNTIME_POLICY_INVALID")
        return normalized

    @field_validator("hybrid_text_weight", "hybrid_semantic_weight")
    @classmethod
    def validate_hybrid_weight(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0 or value > 10:
            raise ValueError("HYBRID_WEIGHT_INVALID")
        return value

    @field_validator("rag_temperature", "rag_top_p", "rag_repeat_penalty")
    @classmethod
    def validate_rag_float(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("RAG_NUMERIC_VALUE_INVALID")
        return value

    @field_validator(
        "hybrid_rrf_k",
        "hybrid_text_weight",
        "hybrid_semantic_weight",
        "hybrid_top_k_default",
        "hybrid_top_k_max",
        "hybrid_candidate_multiplier",
        "rag_top_k_default",
        "rag_top_k_max",
        "rag_context_max_chunks",
        "rag_context_max_tokens",
        "rag_max_new_tokens",
        "rag_token_safety_margin",
        "rag_question_max_length",
        "rag_answer_max_length",
        "rag_temperature",
        "rag_top_p",
        "rag_repeat_penalty",
        "rag_citation_max_sources",
        "rag_source_name_max_length",
        "hpn_matrix_title_max_length",
        "hpn_matrix_description_max_length",
        "hpn_node_title_max_length",
        "hpn_node_statement_max_length",
        "hpn_relation_rationale_max_length",
        "hpn_max_nodes_per_matrix",
        "hpn_max_relations_per_matrix",
        "hpn_max_sources_per_node",
        "hpn_source_name_max_length",
        "graph_max_nodes",
        "graph_max_edges",
        "graph_max_label_length",
        "graph_max_components_detail",
        "graph_max_html_bytes",
        "graph_max_tooltip_length",
        "graph_render_concurrency",
        mode="before",
    )
    @classmethod
    def reject_boolean_hybrid_numbers(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("HYBRID_NUMERIC_VALUE_INVALID")
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
        if self.text_search_default_page_size > self.text_search_max_page_size:
            raise ValueError("TEXT_SEARCH_DEFAULT_PAGE_SIZE no puede superar TEXT_SEARCH_MAX_PAGE_SIZE")
        if self.semantic_search_top_k_default > self.semantic_search_top_k_max:
            raise ValueError(
                "SEMANTIC_SEARCH_TOP_K_DEFAULT no puede superar SEMANTIC_SEARCH_TOP_K_MAX"
            )
        if self.hybrid_top_k_default > self.hybrid_top_k_max:
            raise ValueError("HYBRID_TOP_K_DEFAULT no puede superar HYBRID_TOP_K_MAX")
        if self.rag_top_k_default > self.rag_top_k_max:
            raise ValueError("RAG_TOP_K_DEFAULT no puede superar RAG_TOP_K_MAX")
        if self.rag_top_k_max > self.hybrid_top_k_max:
            raise ValueError("RAG_TOP_K_MAX no puede superar HYBRID_TOP_K_MAX")
        if self.rag_context_max_chunks > self.rag_top_k_max:
            raise ValueError("RAG_CONTEXT_MAX_CHUNKS no puede superar RAG_TOP_K_MAX")
        if self.rag_citation_max_sources > self.rag_context_max_chunks:
            raise ValueError(
                "RAG_CITATION_MAX_SOURCES no puede superar RAG_CONTEXT_MAX_CHUNKS"
            )
        reserved = self.rag_max_new_tokens + self.rag_token_safety_margin
        if reserved >= self.local_llm_context_size:
            raise ValueError("RAG_TOKEN_BUDGET_INVALID")
        if self.rag_context_max_tokens >= self.local_llm_context_size:
            raise ValueError("RAG_CONTEXT_MAX_TOKENS debe ser menor que LOCAL_LLM_CONTEXT_SIZE")
        if self.graph_max_nodes > self.hpn_max_nodes_per_matrix:
            raise ValueError("GRAPH_CONFIGURATION_INVALID")
        if self.graph_max_edges > self.hpn_max_relations_per_matrix:
            raise ValueError("GRAPH_CONFIGURATION_INVALID")
        if self.graph_max_label_length > self.hpn_node_title_max_length:
            raise ValueError("GRAPH_CONFIGURATION_INVALID")
        if self.graph_max_components_detail > self.graph_max_nodes:
            raise ValueError("GRAPH_CONFIGURATION_INVALID")
        return self

    @property
    def log_file_path(self) -> Path:
        """Devuelve la ruta absoluta del archivo de log."""

        directory = self.log_dir
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory
        return (directory / self.log_file_name).resolve()


settings = Settings()
