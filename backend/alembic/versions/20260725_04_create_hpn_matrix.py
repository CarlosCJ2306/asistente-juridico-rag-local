"""Create manual HPN matrices.

Revision ID: 20260725_04
Revises: 20260724_03
Create Date: 2026-07-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260725_04"
down_revision = "20260724_03"
branch_labels = None
depends_on = None

SOURCE_OWNER_INSERT_TRIGGER = "trg_hpn_node_sources_owner_insert"
SOURCE_OWNER_UPDATE_TRIGGER = "trg_hpn_node_sources_owner_update"


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    """Crea exclusivamente la persistencia HPN manual."""

    op.create_table(
        "hpn_matrices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            _enum("draft", "in_review", "reviewed", "archived", name="hpn_matrix_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hpn_matrices_status", "hpn_matrices", ["status"])

    op.create_table(
        "hpn_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matrix_id", sa.Uuid(), nullable=False),
        sa.Column(
            "node_type",
            _enum("fact", "evidence", "norm", name="hpn_node_type"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "review_status",
            _enum("draft", "reviewed", "rejected", name="hpn_node_review_status"),
            nullable=False,
        ),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("display_order >= 1", name="ck_hpn_nodes_display_order_positive"),
        sa.ForeignKeyConstraint(["matrix_id"], ["hpn_matrices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hpn_nodes_matrix_id", "hpn_nodes", ["matrix_id"])
    op.create_index("ix_hpn_nodes_node_type", "hpn_nodes", ["node_type"])
    op.create_index("ix_hpn_nodes_review_status", "hpn_nodes", ["review_status"])

    op.create_table(
        "hpn_node_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column(
            "document_type",
            _enum(
                "expediente",
                "normativa",
                "jurisprudencia",
                "otro",
                name="hpn_source_document_type",
            ),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("chunk_index >= 1", name="ck_hpn_sources_chunk_index_positive"),
        sa.CheckConstraint("start_page >= 1", name="ck_hpn_sources_start_page_positive"),
        sa.CheckConstraint("end_page >= start_page", name="ck_hpn_sources_page_range"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_id"], ["hpn_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hpn_node_sources_node_id", "hpn_node_sources", ["node_id"])
    op.create_index("ix_hpn_node_sources_document_id", "hpn_node_sources", ["document_id"])
    op.create_index("ix_hpn_node_sources_chunk_id", "hpn_node_sources", ["chunk_id"])
    op.create_index(
        "uq_hpn_node_sources_active_chunk",
        "hpn_node_sources",
        ["node_id", "chunk_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        f"""
        CREATE TRIGGER {SOURCE_OWNER_INSERT_TRIGGER}
        BEFORE INSERT ON hpn_node_sources
        FOR EACH ROW
        WHEN NOT EXISTS (
            SELECT 1 FROM document_chunks
            WHERE id = NEW.chunk_id AND document_id = NEW.document_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'HPN_SOURCE_DOCUMENT_CHUNK_MISMATCH');
        END
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {SOURCE_OWNER_UPDATE_TRIGGER}
        BEFORE UPDATE OF chunk_id, document_id ON hpn_node_sources
        FOR EACH ROW
        WHEN NOT EXISTS (
            SELECT 1 FROM document_chunks
            WHERE id = NEW.chunk_id AND document_id = NEW.document_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'HPN_SOURCE_DOCUMENT_CHUNK_MISMATCH');
        END
        """
    )

    op.create_table(
        "hpn_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matrix_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column(
            "relation_type",
            _enum(
                "evidence_supports_fact",
                "evidence_contradicts_fact",
                "norm_applies_to_fact",
                "norm_limits_fact",
                name="hpn_relation_type",
            ),
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            _enum("draft", "reviewed", "rejected", name="hpn_relation_review_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("source_node_id <> target_node_id", name="ck_hpn_relations_not_self"),
        sa.ForeignKeyConstraint(["matrix_id"], ["hpn_matrices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["hpn_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["hpn_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hpn_relations_matrix_id", "hpn_relations", ["matrix_id"])
    op.create_index("ix_hpn_relations_source_node_id", "hpn_relations", ["source_node_id"])
    op.create_index("ix_hpn_relations_target_node_id", "hpn_relations", ["target_node_id"])
    op.create_index("ix_hpn_relations_review_status", "hpn_relations", ["review_status"])
    op.create_index(
        "uq_hpn_relations_active",
        "hpn_relations",
        ["source_node_id", "target_node_id", "relation_type"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Retira solo las tablas, triggers e índices de la Fase 10."""

    op.drop_table("hpn_relations")
    op.execute(f"DROP TRIGGER IF EXISTS {SOURCE_OWNER_UPDATE_TRIGGER}")
    op.execute(f"DROP TRIGGER IF EXISTS {SOURCE_OWNER_INSERT_TRIGGER}")
    op.drop_table("hpn_node_sources")
    op.drop_table("hpn_nodes")
    op.drop_table("hpn_matrices")
