"""Persistencia manual y revisable de matrices HPN."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import DocumentType, UTCDateTime, enum_values, utc_now


class HpnMatrixStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class HpnNodeType(str, Enum):
    FACT = "fact"
    EVIDENCE = "evidence"
    NORM = "norm"


class HpnReviewStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class HpnRelationType(str, Enum):
    EVIDENCE_SUPPORTS_FACT = "evidence_supports_fact"
    EVIDENCE_CONTRADICTS_FACT = "evidence_contradicts_fact"
    NORM_APPLIES_TO_FACT = "norm_applies_to_fact"
    NORM_LIMITS_FACT = "norm_limits_fact"


def _enum(enum_class: type[Enum], name: str, length: int) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        native_enum=False,
        values_callable=enum_values,
        create_constraint=True,
        length=length,
    )


class HpnMatrix(Base):
    __tablename__ = "hpn_matrices"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[HpnMatrixStatus] = mapped_column(
        _enum(HpnMatrixStatus, "hpn_matrix_status", 24),
        nullable=False,
        default=HpnMatrixStatus.DRAFT,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class HpnNode(Base):
    __tablename__ = "hpn_nodes"
    __table_args__ = (
        CheckConstraint("display_order >= 1", name="ck_hpn_nodes_display_order_positive"),
        Index("ix_hpn_nodes_matrix_id", "matrix_id"),
        Index("ix_hpn_nodes_node_type", "node_type"),
        Index("ix_hpn_nodes_review_status", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    matrix_id: Mapped[UUID] = mapped_column(
        ForeignKey("hpn_matrices.id", ondelete="CASCADE"), nullable=False
    )
    node_type: Mapped[HpnNodeType] = mapped_column(
        _enum(HpnNodeType, "hpn_node_type", 16), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[HpnReviewStatus] = mapped_column(
        _enum(HpnReviewStatus, "hpn_node_review_status", 16),
        nullable=False,
        default=HpnReviewStatus.DRAFT,
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class HpnNodeSource(Base):
    __tablename__ = "hpn_node_sources"
    __table_args__ = (
        CheckConstraint("chunk_index >= 1", name="ck_hpn_sources_chunk_index_positive"),
        CheckConstraint("start_page >= 1", name="ck_hpn_sources_start_page_positive"),
        CheckConstraint("end_page >= start_page", name="ck_hpn_sources_page_range"),
        Index("ix_hpn_node_sources_node_id", "node_id"),
        Index("ix_hpn_node_sources_document_id", "document_id"),
        Index("ix_hpn_node_sources_chunk_id", "chunk_id"),
        Index(
            "uq_hpn_node_sources_active_chunk",
            "node_id",
            "chunk_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("hpn_nodes.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        _enum(DocumentType, "hpn_source_document_type", 32), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class HpnRelation(Base):
    __tablename__ = "hpn_relations"
    __table_args__ = (
        CheckConstraint("source_node_id <> target_node_id", name="ck_hpn_relations_not_self"),
        Index("ix_hpn_relations_matrix_id", "matrix_id"),
        Index("ix_hpn_relations_source_node_id", "source_node_id"),
        Index("ix_hpn_relations_target_node_id", "target_node_id"),
        Index("ix_hpn_relations_review_status", "review_status"),
        Index(
            "uq_hpn_relations_active",
            "source_node_id",
            "target_node_id",
            "relation_type",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    matrix_id: Mapped[UUID] = mapped_column(
        ForeignKey("hpn_matrices.id", ondelete="CASCADE"), nullable=False
    )
    source_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("hpn_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[UUID] = mapped_column(
        ForeignKey("hpn_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[HpnRelationType] = mapped_column(
        _enum(HpnRelationType, "hpn_relation_type", 40), nullable=False
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[HpnReviewStatus] = mapped_column(
        _enum(HpnReviewStatus, "hpn_relation_review_status", 16),
        nullable=False,
        default=HpnReviewStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
