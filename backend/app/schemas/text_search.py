"""Contratos tipados para recuperación textual local, sin contenido completo."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType, KnowledgeLayer
from app.schemas.governance_filters import normalize_knowledge_layers


class TextMatchMode(str, Enum):
    ALL_TERMS = "all_terms"
    ANY_TERM = "any_term"
    PHRASE = "phrase"


class TextSearchRequest(BaseModel):
    """Entrada segura: no acepta sintaxis FTS5 ni filtros internos."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=settings.text_search_query_max_chars)
    match_mode: TextMatchMode = TextMatchMode.ALL_TERMS
    document_id: UUID | None = None
    document_types: list[DocumentType] | None = None
    knowledge_layers: list[KnowledgeLayer] | None = None
    min_page: int | None = Field(default=None, ge=1)
    max_page: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(
        default=settings.text_search_default_page_size,
        ge=1,
        le=settings.text_search_max_page_size,
    )

    @field_validator("query")
    @classmethod
    def reject_empty_or_control_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La consulta no puede estar vacía")
        if any(character.isspace() is False and ord(character) < 32 for character in value):
            raise ValueError("La consulta contiene caracteres de control")
        return value

    @field_validator("document_types")
    @classmethod
    def validate_document_types(cls, value: list[DocumentType] | None) -> list[DocumentType] | None:
        if value is not None and len(value) > settings.text_search_max_document_types:
            raise ValueError("La cantidad de tipos documentales supera el límite permitido")
        return value

    _normalize_knowledge_layers = field_validator("knowledge_layers")(
        normalize_knowledge_layers
    )

    @model_validator(mode="after")
    def validate_page_range(self) -> "TextSearchRequest":
        if self.min_page is not None and self.max_page is not None and self.min_page > self.max_page:
            raise ValueError("min_page no puede superar max_page")
        return self


class TextSearchItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    chunk_index: int
    start_page: int
    end_page: int
    snippet: str
    rank_bm25: float = Field(description="Menor es mejor")


class TextSearchPage(BaseModel):
    items: list[TextSearchItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
