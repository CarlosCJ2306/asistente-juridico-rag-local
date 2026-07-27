"""Contratos públicos del índice y la búsqueda semántica local."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType, KnowledgeLayer
from app.schemas.governance_filters import normalize_knowledge_layers


SemanticIndexStatusName = Literal[
    "not_ready", "ready", "building", "error", "unavailable"
]


class SemanticStatusResponse(BaseModel):
    state: SemanticIndexStatusName
    dependency_available: bool
    embedding_model: str
    embedding_dimension: int | None
    distance_metric: Literal["cosine"] = "cosine"
    indexed_chunks: int = Field(ge=0)
    active_chunks: int = Field(ge=0)
    needs_rebuild: bool
    error_code: str | None = None


class SemanticRebuildResponse(BaseModel):
    state: Literal["ready"] = "ready"
    indexed_chunks: int = Field(ge=0)
    embedding_dimension: int = Field(gt=0)
    distance_metric: Literal["cosine"] = "cosine"


class SemanticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=settings.semantic_query_max_chars)
    top_k: int = Field(
        default=settings.semantic_search_top_k_default,
        ge=1,
        le=settings.semantic_search_top_k_max,
    )
    document_id: UUID | None = None
    document_types: list[DocumentType] | None = None
    knowledge_layers: list[KnowledgeLayer] | None = None
    min_page: int | None = Field(default=None, ge=1)
    max_page: int | None = Field(default=None, ge=1)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La consulta no puede estar vacía")
        if any(ord(character) < 32 and not character.isspace() for character in value):
            raise ValueError("La consulta contiene caracteres de control")
        return value

    @field_validator("document_types")
    @classmethod
    def validate_document_types(
        cls, value: list[DocumentType] | None
    ) -> list[DocumentType] | None:
        if value is not None and len(value) > settings.semantic_max_document_types:
            raise ValueError("La cantidad de tipos documentales supera el límite permitido")
        return value

    _normalize_knowledge_layers = field_validator("knowledge_layers")(
        normalize_knowledge_layers
    )

    @model_validator(mode="after")
    def validate_page_range(self) -> "SemanticSearchRequest":
        if (
            self.min_page is not None
            and self.max_page is not None
            and self.min_page > self.max_page
        ):
            raise ValueError("min_page no puede superar max_page")
        return self


class SemanticSearchItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    chunk_index: int = Field(ge=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    snippet: str
    distance_cosine: float = Field(description="Menor es mejor; no es probabilidad")


class SemanticSearchResponse(BaseModel):
    items: list[SemanticSearchItem]
    returned: int = Field(ge=0)
    top_k: int = Field(ge=1)
