"""Create document pages and chunks.

Revision ID: 20260723_02
Revises: 20260723_01
Create Date: 2026-07-23 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723_02"
down_revision = "20260723_01"
branch_labels = None
depends_on = None


def _document_status_type() -> sa.Enum:
    return sa.Enum(
        "registered",
        "stored",
        "pending_extraction",
        "extracting",
        "extracted",
        "extraction_failed",
        "failed",
        "archived",
        name="document_status",
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    """Añade persistencia de extracción y amplía los estados documentales."""

    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(
                "registered", "stored", "pending_extraction", "failed", "archived",
                name="document_status", native_enum=False, create_constraint=True,
            ),
            type_=_document_status_type(),
            existing_nullable=False,
        )
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_number"),
        sa.CheckConstraint("page_number >= 1", name="ck_document_pages_page_number_positive"),
        sa.CheckConstraint("char_count >= 0", name="ck_document_pages_char_count_nonnegative"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_index"),
        sa.CheckConstraint("chunk_index >= 1", name="ck_document_chunks_index_positive"),
        sa.CheckConstraint("char_count >= 0", name="ck_document_chunks_char_count_nonnegative"),
        sa.CheckConstraint("word_count >= 0", name="ck_document_chunks_word_count_nonnegative"),
        sa.CheckConstraint("start_page >= 1", name="ck_document_chunks_start_page_positive"),
        sa.CheckConstraint("end_page >= 1", name="ck_document_chunks_end_page_positive"),
        sa.CheckConstraint("end_page >= start_page", name="ck_document_chunks_page_range"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    """Elimina solamente los objetos creados en esta revisión."""

    # Normaliza primero los estados que no existen en la revisión histórica.
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'pending_extraction' "
            "WHERE status IN ('extracting', 'extracted')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE documents SET status = 'failed' "
            "WHERE status = 'extraction_failed'"
        )
    )
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_document_pages_document_id", table_name="document_pages")
    op.drop_table("document_pages")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=_document_status_type(),
            type_=sa.Enum(
                "registered", "stored", "pending_extraction", "failed", "archived",
                name="document_status", native_enum=False, create_constraint=True,
            ),
            existing_nullable=False,
        )
