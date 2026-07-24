"""Chunks jurídicos deterministas derivados de páginas extraídas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import UTCDateTime, utc_now


class DocumentChunk(Base):
    """Fragmento trazable de texto limpio sin embeddings ni semántica."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_index"),
        CheckConstraint("chunk_index >= 1", name="ck_document_chunks_index_positive"),
        CheckConstraint("char_count >= 0", name="ck_document_chunks_char_count_nonnegative"),
        CheckConstraint("word_count >= 0", name="ck_document_chunks_word_count_nonnegative"),
        CheckConstraint("start_page >= 1", name="ck_document_chunks_start_page_positive"),
        CheckConstraint("end_page >= 1", name="ck_document_chunks_end_page_positive"),
        CheckConstraint("end_page >= start_page", name="ck_document_chunks_page_range"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
