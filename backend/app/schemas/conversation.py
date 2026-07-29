"""Contratos públicos del historial RAG persistente."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.database.models.document import DocumentType, KnowledgeLayer
from app.schemas.rag_chat import RagChatRequest


def _plain_bounded(value: str, *, code: str) -> str:
    normalized = " ".join(value.split())
    if (
        not normalized
        or any(unicodedata.category(character).startswith("C") for character in value)
        or "<" in normalized
        or ">" in normalized
    ):
        raise ValueError(code)
    return normalized


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=settings.conversation_title_max_length)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _plain_bounded(value, code="CONVERSATION_TITLE_INVALID")


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=settings.conversation_title_max_length)
    status: Literal["active", "archived"] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _plain_bounded(value, code="CONVERSATION_TITLE_INVALID")

    @model_validator(mode="after")
    def require_change(self) -> "ConversationUpdate":
        if self.title is None and self.status is None:
            raise ValueError("CONVERSATION_UPDATE_EMPTY")
        return self


class ConversationMessageCreate(RagChatRequest):
    """Reutiliza exactamente los filtros de la pregunta individual."""


class ConversationCitationRead(BaseModel):
    id: UUID
    marker: str
    document_id: UUID
    display_name: str
    document_type: DocumentType
    knowledge_layer: KnowledgeLayer
    issuing_entity: str | None
    document_date: datetime | None
    start_page: int
    end_page: int
    chunk_index: int
    locator_label: str | None
    direct_quote: str
    quote_truncated: bool
    citation_order: int
    document_available: bool


class ConversationClaimRead(BaseModel):
    id: UUID
    statement: str
    claim_order: int
    supported: bool
    citation_ids: list[UUID]


class ConversationMessageRead(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    sequence_number: int
    public_status: Literal["answered", "partial", "insufficient_context", "failed"] | None
    coverage_status: Literal["full", "partial", "insufficient"] | None
    created_at: datetime
    completed_at: datetime | None
    error_code: str | None
    citations: list[ConversationCitationRead] = Field(default_factory=list)
    claims: list[ConversationClaimRead] = Field(default_factory=list)
    unsupported_points: list[str] = Field(default_factory=list)


class ConversationRead(BaseModel):
    id: UUID
    title: str
    owner_type: Literal["guest", "account"]
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    expires_at: datetime | None
    message_count: int = 0


class ConversationDetail(ConversationRead):
    messages: list[ConversationMessageRead]


class ConversationPage(BaseModel):
    items: list[ConversationRead]
    total: int
    page: int
    page_size: int


class ConversationTurnResponse(BaseModel):
    conversation: ConversationRead
    user_message: ConversationMessageRead
    assistant_message: ConversationMessageRead


IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,63}")
