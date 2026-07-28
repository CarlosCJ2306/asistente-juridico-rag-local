"""Create persistent local document processing queue.

Revision ID: 20260728_07
Revises: 20260727_06
Create Date: 2026-07-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260728_07"
down_revision = "20260727_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade una cola técnica sin modificar tablas documentales existentes."""

    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_layer", sa.String(length=32), nullable=False),
        sa.Column("public_name", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("inbox_relative_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_document_processing_jobs_attempts"),
        sa.CheckConstraint(
            "knowledge_layer IN ('private_library','temporary')",
            name="ck_document_processing_jobs_layer",
        ),
        sa.CheckConstraint(
            "operation IN ('inbox_import','upload_pipeline')",
            name="ck_document_processing_jobs_operation",
        ),
        sa.CheckConstraint(
            "state IN ('queued','detecting','registering','extracting',"
            "'waiting_for_index','indexing','completed','failed','quarantined')",
            name="ck_document_processing_jobs_state",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_processing_jobs_state_created",
        "document_processing_jobs",
        ["state", "created_at"],
    )
    op.create_index(
        "ix_document_processing_jobs_document_id",
        "document_processing_jobs",
        ["document_id"],
    )
    op.create_index(
        "uq_document_processing_jobs_active_inbox_path",
        "document_processing_jobs",
        ["inbox_relative_path"],
        unique=True,
        sqlite_where=sa.text(
            "inbox_relative_path IS NOT NULL AND state IN "
            "('queued','detecting','registering','extracting','waiting_for_index','indexing')"
        ),
    )


def downgrade() -> None:
    """Retira solo la cola derivada, conservando documentos e índices."""

    op.drop_index(
        "uq_document_processing_jobs_active_inbox_path",
        table_name="document_processing_jobs",
    )
    op.drop_index(
        "ix_document_processing_jobs_document_id",
        table_name="document_processing_jobs",
    )
    op.drop_index(
        "ix_document_processing_jobs_state_created",
        table_name="document_processing_jobs",
    )
    op.drop_table("document_processing_jobs")
