"""Contratos públicos del chat RAG local con citas estructurales."""

from __future__ import annotations

import unicodedata
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType, KnowledgeLayer
from app.schemas.governance_filters import normalize_knowledge_layers
from app.schemas.text_search import TextMatchMode


class RagChatRequest(BaseModel):
    """Pregunta y filtros controlados; no acepta parámetros de generación."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=min(
            settings.rag_question_max_length,
            settings.text_search_query_max_chars,
            settings.semantic_query_max_chars,
        ),
    )
    text_match_mode: TextMatchMode = TextMatchMode.ALL_TERMS
    top_k: int = Field(default=settings.rag_top_k_default, ge=1, le=settings.rag_top_k_max)
    document_id: UUID | None = None
    document_types: list[DocumentType] | None = None
    knowledge_layers: list[KnowledgeLayer] | None = None
    min_page: int | None = Field(default=None, ge=1)
    max_page: int | None = Field(default=None, ge=1)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("La pregunta no puede estar vacía")
        if any(unicodedata.category(character).startswith("C") for character in value):
            raise ValueError("La pregunta contiene caracteres de control")
        return normalized

    @field_validator("top_k", "min_page", "max_page", mode="before")
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("El valor debe ser entero")
        return value

    @field_validator("document_types")
    @classmethod
    def validate_document_types(
        cls, value: list[DocumentType] | None
    ) -> list[DocumentType] | None:
        if value is not None and len(value) > min(
            settings.text_search_max_document_types,
            settings.semantic_max_document_types,
        ):
            raise ValueError("La cantidad de tipos documentales supera el límite")
        return value

    _normalize_knowledge_layers = field_validator("knowledge_layers")(
        normalize_knowledge_layers
    )

    @model_validator(mode="after")
    def validate_pages(self) -> "RagChatRequest":
        if self.min_page is not None and self.max_page is not None:
            if self.min_page > self.max_page:
                raise ValueError("min_page no puede superar max_page")
        return self


class RagCitation(BaseModel):
    """Referencia pública construida exclusivamente desde SQLite."""

    model_config = ConfigDict(extra="forbid")

    marker: str = Field(pattern=r"^\[F[1-9]\d*\]$", max_length=16)
    document_id: UUID
    document_name: str = Field(min_length=1, max_length=settings.rag_source_name_max_length)
    display_name: str = Field(default="Documento", min_length=1, max_length=settings.rag_source_name_max_length)
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer = KnowledgeLayer.PRIVATE_LIBRARY
    chunk_index: int = Field(ge=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)

    @field_validator("chunk_index", "start_page", "end_page", mode="before")
    @classmethod
    def reject_boolean_citation_integers(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("RAG_CITATION_METADATA_INVALID")
        return value

    @model_validator(mode="after")
    def validate_pages(self) -> "RagCitation":
        if self.end_page < self.start_page:
            raise ValueError("RAG_CITATION_METADATA_INVALID")
        return self


class RagChatResponse(BaseModel):
    """Respuesta sin prompt, contexto, scores ni identificadores de chunk."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "insufficient_context"]
    answer: str = Field(min_length=1, max_length=settings.rag_answer_max_length)
    retrieved_chunks: int = Field(ge=0)
    context_chunks: int = Field(ge=0, le=settings.rag_context_max_chunks)
    context_tokens: int = Field(ge=0, le=settings.rag_context_max_tokens)
    requires_professional_review: Literal[True] = True
    citation_count: int = Field(ge=0, le=settings.rag_citation_max_sources)
    citations: list[RagCitation] = Field(
        default_factory=list,
        max_length=settings.rag_citation_max_sources,
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "RagChatResponse":
        if self.context_chunks > self.retrieved_chunks:
            raise ValueError("RAG_RESPONSE_COUNT_INVALID")
        if self.citation_count != len(self.citations):
            raise ValueError("RAG_CITATION_COUNT_INVALID")
        if self.citation_count > self.context_chunks:
            raise ValueError("RAG_CITATION_COUNT_INVALID")
        markers = [citation.marker for citation in self.citations]
        if len(markers) != len(set(markers)):
            raise ValueError("RAG_CITATION_DUPLICATE")
        source_identities = [
            (citation.document_id, citation.chunk_index)
            for citation in self.citations
        ]
        if len(source_identities) != len(set(source_identities)):
            raise ValueError("RAG_CITATION_DUPLICATE")
        if self.status == "insufficient_context" and (
            self.context_chunks != 0
            or self.context_tokens != 0
            or self.citation_count != 0
            or self.citations
        ):
            raise ValueError("RAG_INSUFFICIENT_CONTEXT_INVALID")
        if self.status == "answered" and self.citation_count == 0:
            raise ValueError("RAG_CITATION_OUTPUT_INVALID")
        if self.status == "answered":
            answer_markers = re.findall(r"\[F[1-9]\d*\]", self.answer)
            if list(dict.fromkeys(answer_markers)) != markers:
                raise ValueError("RAG_CITATION_OUTPUT_INVALID")
        return self
