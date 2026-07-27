"""Create managed corpus import registry.

Revision ID: 20260727_06
Revises: 20260726_05
Create Date: 2026-07-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260727_06"
down_revision = "20260726_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade solo trazabilidad técnica de importaciones administradas."""

    op.create_table(
        "managed_corpus_entries",
        sa.Column("corpus_id", sa.String(length=120), nullable=False),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("corpus_id", "source_key"),
        sa.UniqueConstraint(
            "document_id", name="uq_managed_corpus_entries_document_id"
        ),
    )


def downgrade() -> None:
    """Retira únicamente el registro de importación administrada."""

    op.drop_table("managed_corpus_entries")
