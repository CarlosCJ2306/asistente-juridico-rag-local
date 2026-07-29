"""Create explicit CaseDocument membership.

Revision ID: 20260729_10
Revises: 20260728_09
Create Date: 2026-07-29 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260729_10"
down_revision = "20260728_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade solo asociaciones documentales explícitas, sin backfill."""

    op.create_table(
        "case_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("snapshot_display_name", sa.String(length=255), nullable=False),
        sa.Column("snapshot_document_type", sa.String(length=32), nullable=False),
        sa.Column("snapshot_knowledge_layer", sa.String(length=32), nullable=False),
        sa.Column("snapshot_source_kind", sa.String(length=32), nullable=False),
        sa.Column("snapshot_review_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_legal_validity_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_extraction_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_index_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot_expires_at", sa.DateTime(), nullable=True),
        sa.Column("snapshot_document_updated_at", sa.DateTime(), nullable=False),
        sa.Column("snapshot_document_version_label", sa.String(length=120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("attached_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('primary_record','annex','evidence','other')",
            name="ck_case_documents_purpose",
        ),
        sa.CheckConstraint(
            "display_order BETWEEN 0 AND 1000000",
            name="ck_case_documents_display_order",
        ),
        sa.CheckConstraint("version >= 1", name="ck_case_documents_version"),
        sa.CheckConstraint(
            "updated_at >= attached_at AND (removed_at IS NULL OR removed_at >= attached_at)",
            name="ck_case_documents_timestamps",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_case_documents_public_id"),
    )
    op.create_index("ix_case_documents_case_id", "case_documents", ["case_id"])
    op.create_index("ix_case_documents_document_id", "case_documents", ["document_id"])
    op.create_index(
        "ix_case_documents_case_order", "case_documents", ["case_id", "display_order"]
    )
    op.create_index(
        "ix_case_documents_case_removed", "case_documents", ["case_id", "removed_at"]
    )
    op.create_index("ix_case_documents_attached_at", "case_documents", ["attached_at"])
    op.create_index(
        "uq_case_documents_active_case_document",
        "case_documents",
        ["case_id", "document_id"],
        unique=True,
        sqlite_where=sa.text("removed_at IS NULL"),
    )


def downgrade() -> None:
    """Retira solo CaseDocument y conserva Case y documentos."""

    op.drop_index(
        "uq_case_documents_active_case_document", table_name="case_documents"
    )
    op.drop_index("ix_case_documents_attached_at", table_name="case_documents")
    op.drop_index("ix_case_documents_case_removed", table_name="case_documents")
    op.drop_index("ix_case_documents_case_order", table_name="case_documents")
    op.drop_index("ix_case_documents_document_id", table_name="case_documents")
    op.drop_index("ix_case_documents_case_id", table_name="case_documents")
    op.drop_table("case_documents")
