"""Conversaciones RAG persistentes sin prompts ni razonamiento interno."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import UTCDateTime, enum_values, utc_now


class ConversationOwnerType(str, Enum):
    GUEST = "guest"
    ACCOUNT = "account"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConversationMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationMessageStatus(str, Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    FAILED = "failed"


class ConversationCoverageStatus(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "(owner_type = 'guest' AND guest_session_hash IS NOT NULL "
            "AND user_id IS NULL AND expires_at IS NOT NULL) OR "
            "(owner_type = 'account' AND user_id IS NOT NULL "
            "AND guest_session_hash IS NULL)",
            name="ck_conversations_owner",
        ),
        CheckConstraint("schema_version >= 1", name="ck_conversations_schema_version"),
        Index(
            "ix_conversations_guest_activity",
            "guest_session_hash",
            "status",
            "last_activity_at",
        ),
        Index("ix_conversations_user_activity", "user_id", "status", "last_activity_at"),
        Index("ix_conversations_guest_expiration", "owner_type", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_type: Mapped[ConversationOwnerType] = mapped_column(
        SqlEnum(
            ConversationOwnerType,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=16,
        ),
        nullable=False,
    )
    guest_session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        SqlEnum(
            ConversationStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=16,
        ),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("sequence_number >= 1", name="ck_conversation_messages_sequence"),
        CheckConstraint(
            "(role = 'user' AND public_status IS NULL AND coverage_status IS NULL) OR "
            "(role = 'assistant' AND public_status IS NOT NULL)",
            name="ck_conversation_messages_role_status",
        ),
        UniqueConstraint(
            "conversation_id", "sequence_number", name="uq_conversation_messages_sequence"
        ),
        UniqueConstraint(
            "conversation_id", "idempotency_key", name="uq_conversation_messages_idempotency"
        ),
        Index("ix_conversation_messages_conversation", "conversation_id", "sequence_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[ConversationMessageRole] = mapped_column(
        SqlEnum(
            ConversationMessageRole,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=16,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    public_status: Mapped[ConversationMessageStatus | None] = mapped_column(
        SqlEnum(
            ConversationMessageStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=32,
        ),
        nullable=True,
    )
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    coverage_status: Mapped[ConversationCoverageStatus | None] = mapped_column(
        SqlEnum(
            ConversationCoverageStatus,
            native_enum=False,
            values_callable=enum_values,
            create_constraint=True,
            length=16,
        ),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConversationCitation(Base):
    __tablename__ = "conversation_citations"
    __table_args__ = (
        CheckConstraint("start_page >= 1", name="ck_conversation_citations_start_page"),
        CheckConstraint("end_page >= start_page", name="ck_conversation_citations_page_range"),
        CheckConstraint("chunk_index >= 1", name="ck_conversation_citations_chunk_index"),
        CheckConstraint("citation_order >= 1", name="ck_conversation_citations_order"),
        UniqueConstraint(
            "assistant_message_id", "marker", name="uq_conversation_citations_marker"
        ),
        UniqueConstraint(
            "assistant_message_id", "citation_order", name="uq_conversation_citations_order"
        ),
        Index("ix_conversation_citations_message", "assistant_message_id", "citation_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    assistant_message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    marker: Mapped[str] = mapped_column(String(16), nullable=False)
    document_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_layer_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    issuing_entity_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_date_snapshot: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    locator_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direct_quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    citation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class ConversationClaim(Base):
    __tablename__ = "conversation_claims"
    __table_args__ = (
        CheckConstraint("claim_order >= 1", name="ck_conversation_claims_order"),
        UniqueConstraint(
            "assistant_message_id", "claim_order", name="uq_conversation_claims_order"
        ),
        Index("ix_conversation_claims_message", "assistant_message_id", "claim_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    assistant_message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_order: Mapped[int] = mapped_column(Integer, nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class ConversationClaimCitation(Base):
    __tablename__ = "conversation_claim_citations"

    claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_claims.id", ondelete="CASCADE"),
        primary_key=True,
    )
    citation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversation_citations.id", ondelete="CASCADE"),
        primary_key=True,
    )
