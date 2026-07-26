"""Add foundational document governance metadata.

Revision ID: 20260726_05
Revises: 20260725_04
Create Date: 2026-07-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260726_05"
down_revision = "20260725_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade metadatos de gobernanza sin reconstruir las tablas documentales."""

    op.add_column(
        "documents",
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=False,
            server_default="Documento",
        ),
    )
    op.execute("UPDATE documents SET display_name = original_filename")
    op.execute(
        "ALTER TABLE documents ADD COLUMN knowledge_layer VARCHAR(32) "
        "NOT NULL DEFAULT 'private_library' "
        "CONSTRAINT ck_documents_knowledge_layer CHECK (knowledge_layer IN "
        "('managed_corpus','private_library','temporary','web_verified','global_candidate'))"
    )
    op.execute(
        "ALTER TABLE documents ADD COLUMN source_kind VARCHAR(32) "
        "NOT NULL DEFAULT 'local_upload' "
        "CONSTRAINT ck_documents_source_kind CHECK (source_kind IN "
        "('local_upload','managed_import','web_import'))"
    )
    op.execute(
        "ALTER TABLE documents ADD COLUMN review_status VARCHAR(32) "
        "NOT NULL DEFAULT 'not_required' "
        "CONSTRAINT ck_documents_review_status CHECK (review_status IN "
        "('not_required','pending','approved','rejected','archived'))"
    )
    op.execute(
        "ALTER TABLE documents ADD COLUMN legal_validity_status VARCHAR(32) "
        "NOT NULL DEFAULT 'unknown' "
        "CONSTRAINT ck_documents_legal_validity_status CHECK (legal_validity_status IN "
        "('unknown','current','superseded','repealed','expired'))"
    )
    op.execute(
        "ALTER TABLE documents ADD COLUMN index_status VARCHAR(32) "
        "NOT NULL DEFAULT 'not_requested' "
        "CONSTRAINT ck_documents_index_status CHECK (index_status IN "
        "('not_requested','pending','indexing','indexed','failed','excluded'))"
    )
    op.add_column("documents", sa.Column("issuing_entity", sa.String(255)))
    op.add_column("documents", sa.Column("jurisdiction", sa.String(120)))
    op.add_column("documents", sa.Column("legal_area", sa.String(120)))
    op.add_column("documents", sa.Column("canonical_source_url", sa.String(2048)))
    op.add_column("documents", sa.Column("published_at", sa.DateTime()))
    op.add_column("documents", sa.Column("source_accessed_at", sa.DateTime()))
    op.add_column("documents", sa.Column("version_label", sa.String(120)))
    op.add_column("documents", sa.Column("expires_at", sa.DateTime()))
    op.add_column("documents", sa.Column("archived_at", sa.DateTime()))
    op.add_column("documents", sa.Column("archive_reason", sa.String(500)))
    op.add_column("documents", sa.Column("rejection_reason", sa.String(500)))
    op.execute(
        "ALTER TABLE documents ADD COLUMN supersedes_document_id CHAR(32) "
        "REFERENCES documents(id) ON DELETE RESTRICT"
    )
    op.execute(
        """
        CREATE TRIGGER trg_documents_supersedes_not_self_insert
        BEFORE INSERT ON documents
        FOR EACH ROW
        WHEN NEW.supersedes_document_id = NEW.id
        BEGIN
            SELECT RAISE(ABORT, 'DOCUMENT_SUPERSEDES_SELF');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_documents_supersedes_not_self_update
        BEFORE UPDATE OF supersedes_document_id ON documents
        FOR EACH ROW
        WHEN NEW.supersedes_document_id = NEW.id
        BEGIN
            SELECT RAISE(ABORT, 'DOCUMENT_SUPERSEDES_SELF');
        END
        """
    )

    op.create_index(
        "ix_documents_knowledge_layer_deleted",
        "documents",
        ["knowledge_layer", "is_deleted"],
    )
    op.create_index("ix_documents_review_status", "documents", ["review_status"])
    op.create_index(
        "ix_documents_legal_validity_status",
        "documents",
        ["legal_validity_status"],
    )
    op.create_index("ix_documents_index_status", "documents", ["index_status"])
    op.create_index("ix_documents_expires_at", "documents", ["expires_at"])
    op.create_index(
        "ix_documents_supersedes_document_id",
        "documents",
        ["supersedes_document_id"],
    )


def downgrade() -> None:
    """Retira solo los metadatos de gobernanza añadidos por esta revisión."""

    op.drop_index("ix_documents_supersedes_document_id", table_name="documents")
    op.drop_index("ix_documents_expires_at", table_name="documents")
    op.drop_index("ix_documents_index_status", table_name="documents")
    op.drop_index("ix_documents_legal_validity_status", table_name="documents")
    op.drop_index("ix_documents_review_status", table_name="documents")
    op.drop_index("ix_documents_knowledge_layer_deleted", table_name="documents")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_supersedes_not_self_update")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_supersedes_not_self_insert")

    for column_name in (
        "supersedes_document_id",
        "rejection_reason",
        "archive_reason",
        "archived_at",
        "expires_at",
        "version_label",
        "source_accessed_at",
        "published_at",
        "canonical_source_url",
        "legal_area",
        "jurisdiction",
        "issuing_entity",
        "index_status",
        "legal_validity_status",
        "review_status",
        "source_kind",
        "knowledge_layer",
        "display_name",
    ):
        op.execute(f"ALTER TABLE documents DROP COLUMN {column_name}")
