"""Contratos tipados para recuperación híbrida local mediante RRF."""

from __future__ import annotations

import math
import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType, KnowledgeLayer
from app.schemas.governance_filters import normalize_knowledge_layers
from app.schemas.text_search import TextMatchMode


class HybridSearchRequest(BaseModel):
    """Entrada común para las fuentes textual y semántica."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=min(
            settings.text_search_query_max_chars,
            settings.semantic_query_max_chars,
        ),
    )
    text_match_mode: TextMatchMode = TextMatchMode.ALL_TERMS
    top_k: int = Field(
        default=settings.hybrid_top_k_default,
        ge=1,
        le=settings.hybrid_top_k_max,
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
        if any(
            unicodedata.category(character).startswith("C")
            for character in value
        ):
            raise ValueError("La consulta contiene caracteres de control")
        if len(value.split()) > settings.text_search_max_terms:
            raise ValueError("La consulta supera la cantidad máxima de términos")
        return value

    @field_validator("top_k", mode="before")
    @classmethod
    def reject_boolean_top_k(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("top_k debe ser un entero")
        return value

    @field_validator("document_types")
    @classmethod
    def validate_document_types(
        cls, value: list[DocumentType] | None
    ) -> list[DocumentType] | None:
        limit = min(
            settings.text_search_max_document_types,
            settings.semantic_max_document_types,
        )
        if value is not None and len(value) > limit:
            raise ValueError("La cantidad de tipos documentales supera el límite permitido")
        return value

    _normalize_knowledge_layers = field_validator("knowledge_layers")(
        normalize_knowledge_layers
    )

    @model_validator(mode="after")
    def validate_page_range(self) -> "HybridSearchRequest":
        if (
            self.min_page is not None
            and self.max_page is not None
            and self.min_page > self.max_page
        ):
            raise ValueError("min_page no puede superar max_page")
        return self


class HybridSearchItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_name: str = Field(default="Documento", min_length=1, max_length=255)
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    chunk_index: int = Field(ge=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    snippet: str
    hybrid_score: float = Field(
        gt=0,
        description="Mayor es mejor según RRF; no representa probabilidad",
    )
    appeared_in_text: bool
    appeared_in_semantic: bool
    text_rank: int | None = Field(default=None, ge=1)
    semantic_rank: int | None = Field(default=None, ge=1)
    rank_bm25: float | None = Field(
        default=None,
        description="Menor es mejor; no representa probabilidad",
    )
    distance_cosine: float | None = Field(
        default=None,
        description="Menor es mejor; no representa probabilidad",
    )

    @field_validator(
        "chunk_index",
        "start_page",
        "end_page",
        "text_rank",
        "semantic_rank",
        mode="before",
    )
    @classmethod
    def reject_boolean_integer_fields(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("El valor debe ser entero")
        return value

    @field_validator(
        "hybrid_score",
        "rank_bm25",
        "distance_cosine",
        mode="before",
    )
    @classmethod
    def reject_boolean_scores(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("El score debe ser numérico")
        return value

    @field_validator("hybrid_score", "rank_bm25", "distance_cosine")
    @classmethod
    def validate_finite_scores(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("El score debe ser finito")
        return value

    @model_validator(mode="after")
    def validate_source_traceability(self) -> "HybridSearchItem":
        if self.appeared_in_text != (
            self.text_rank is not None and self.rank_bm25 is not None
        ):
            raise ValueError("HYBRID_TEXT_TRACE_INVALID")
        if self.appeared_in_semantic != (
            self.semantic_rank is not None and self.distance_cosine is not None
        ):
            raise ValueError("HYBRID_SEMANTIC_TRACE_INVALID")
        return self


class HybridSearchResponse(BaseModel):
    items: list[HybridSearchItem]
    returned: int = Field(ge=0)
    top_k: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_result_count(self) -> "HybridSearchResponse":
        if self.returned != len(self.items) or self.returned > self.top_k:
            raise ValueError("HYBRID_RESPONSE_COUNT_INVALID")
        return self
