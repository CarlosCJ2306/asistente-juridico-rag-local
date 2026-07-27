"""Registro técnico mínimo de importaciones administradas."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.document import UTCDateTime, utc_now


class ManagedCorpusEntry(Base):
    """Vincula una clave versionable del manifiesto con un documento."""

    __tablename__ = "managed_corpus_entries"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_managed_corpus_entries_document_id"),
    )

    corpus_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
