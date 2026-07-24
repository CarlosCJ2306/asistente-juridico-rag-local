"""Create documents table.

Revision ID: 20260723_01
Revises:
Create Date: 2026-07-23 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260723_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla de metadatos documentales e índices asociados."""

    document_type = sa.Enum(
        "expediente",
        "normativa",
        "jurisprudencia",
        "otro",
        name="document_type",
        native_enum=False,
        create_constraint=True,
    )
    document_status = sa.Enum(
        "registered",
        "stored",
        "pending_extraction",
        "failed",
        "archived",
        name="document_status",
        native_enum=False,
        create_constraint=True,
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path", name="uq_documents_relative_path"),
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"], unique=True)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)


def downgrade() -> None:
    """Elimina únicamente los objetos creados por esta revisión."""

    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_table("documents")
