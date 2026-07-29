"""Create persistent guest conversations and citation snapshots.

Revision ID: 20260728_08
Revises: 20260728_07
Create Date: 2026-07-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260728_08"
down_revision = "20260728_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade conversaciones sin modificar documentos ni índices derivados."""

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("guest_session_hash", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("owner_type IN ('guest','account')", name="ck_conversations_owner_type"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_conversations_status"),
        sa.CheckConstraint(
            "(owner_type = 'guest' AND guest_session_hash IS NOT NULL "
            "AND user_id IS NULL AND expires_at IS NOT NULL) OR "
            "(owner_type = 'account' AND user_id IS NOT NULL "
            "AND guest_session_hash IS NULL)",
            name="ck_conversations_owner",
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_conversations_schema_version"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_guest_activity", "conversations", ["guest_session_hash", "status", "last_activity_at"])
    op.create_index("ix_conversations_user_activity", "conversations", ["user_id", "status", "last_activity_at"])
    op.create_index("ix_conversations_guest_expiration", "conversations", ["owner_type", "expires_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("public_status", sa.String(length=32), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("coverage_status", sa.String(length=16), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_conversation_messages_role"),
        sa.CheckConstraint(
            "public_status IS NULL OR public_status IN "
            "('answered','partial','insufficient_context','failed')",
            name="ck_conversation_messages_status",
        ),
        sa.CheckConstraint(
            "coverage_status IS NULL OR coverage_status IN ('full','partial','insufficient')",
            name="ck_conversation_messages_coverage",
        ),
        sa.CheckConstraint("sequence_number >= 1", name="ck_conversation_messages_sequence"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 12000", name="ck_conversation_messages_content"),
        sa.CheckConstraint(
            "(role = 'user' AND public_status IS NULL AND coverage_status IS NULL) OR "
            "(role = 'assistant' AND public_status IS NOT NULL)",
            name="ck_conversation_messages_role_status",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence_number", name="uq_conversation_messages_sequence"),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_conversation_messages_idempotency"),
    )
    op.create_index("ix_conversation_messages_conversation", "conversation_messages", ["conversation_id", "sequence_number"])

    op.create_table(
        "conversation_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=False),
        sa.Column("marker", sa.String(length=16), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("display_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("document_type_snapshot", sa.String(length=32), nullable=False),
        sa.Column("knowledge_layer_snapshot", sa.String(length=32), nullable=False),
        sa.Column("issuing_entity_snapshot", sa.String(length=255), nullable=True),
        sa.Column("document_date_snapshot", sa.DateTime(), nullable=True),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("locator_label", sa.String(length=255), nullable=True),
        sa.Column("direct_quote", sa.Text(), nullable=False),
        sa.Column("quote_truncated", sa.Boolean(), nullable=False),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("start_page >= 1", name="ck_conversation_citations_start_page"),
        sa.CheckConstraint("end_page >= start_page", name="ck_conversation_citations_page_range"),
        sa.CheckConstraint("chunk_index >= 1", name="ck_conversation_citations_chunk_index"),
        sa.CheckConstraint("citation_order >= 1", name="ck_conversation_citations_order"),
        sa.CheckConstraint("length(direct_quote) BETWEEN 1 AND 2000", name="ck_conversation_citations_quote"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["conversation_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id", "marker", name="uq_conversation_citations_marker"),
        sa.UniqueConstraint("assistant_message_id", "citation_order", name="uq_conversation_citations_order"),
    )
    op.create_index("ix_conversation_citations_message", "conversation_citations", ["assistant_message_id", "citation_order"])

    op.create_table(
        "conversation_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("claim_order", sa.Integer(), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("claim_order >= 1", name="ck_conversation_claims_order"),
        sa.CheckConstraint("length(statement) BETWEEN 1 AND 6000", name="ck_conversation_claims_statement"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["conversation_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id", "claim_order", name="uq_conversation_claims_order"),
    )
    op.create_index("ix_conversation_claims_message", "conversation_claims", ["assistant_message_id", "claim_order"])

    op.create_table(
        "conversation_claim_citations",
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("citation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["conversation_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["citation_id"], ["conversation_citations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("claim_id", "citation_id"),
    )


def downgrade() -> None:
    """Retira solo el dominio conversacional añadido por esta revisión."""

    op.drop_table("conversation_claim_citations")
    op.drop_index("ix_conversation_claims_message", table_name="conversation_claims")
    op.drop_table("conversation_claims")
    op.drop_index("ix_conversation_citations_message", table_name="conversation_citations")
    op.drop_table("conversation_citations")
    op.drop_index("ix_conversation_messages_conversation", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_guest_expiration", table_name="conversations")
    op.drop_index("ix_conversations_user_activity", table_name="conversations")
    op.drop_index("ix_conversations_guest_activity", table_name="conversations")
    op.drop_table("conversations")
