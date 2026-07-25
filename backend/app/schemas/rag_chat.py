"""Contratos públicos del chat RAG local sin historial ni citas finales."""

from __future__ import annotations

import unicodedata
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType
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

    @model_validator(mode="after")
    def validate_pages(self) -> "RagChatRequest":
        if self.min_page is not None and self.max_page is not None:
            if self.min_page > self.max_page:
                raise ValueError("min_page no puede superar max_page")
        return self


class RagChatResponse(BaseModel):
    """Respuesta sin identificadores, contexto, scores ni referencias finales."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "insufficient_context"]
    answer: str = Field(min_length=1, max_length=settings.rag_answer_max_length)
    retrieved_chunks: int = Field(ge=0)
    context_chunks: int = Field(ge=0, le=settings.rag_context_max_chunks)
    context_tokens: int = Field(ge=0, le=settings.rag_context_max_tokens)
    requires_professional_review: Literal[True] = True

    @model_validator(mode="after")
    def validate_counts(self) -> "RagChatResponse":
        if self.context_chunks > self.retrieved_chunks:
            raise ValueError("RAG_RESPONSE_COUNT_INVALID")
        if self.status == "insufficient_context" and (
            self.context_chunks != 0 or self.context_tokens != 0
        ):
            raise ValueError("RAG_INSUFFICIENT_CONTEXT_INVALID")
        return self
