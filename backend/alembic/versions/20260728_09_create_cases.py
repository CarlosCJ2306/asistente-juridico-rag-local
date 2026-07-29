"""Create persistent Case core and structured audit events.

Revision ID: 20260728_09
Revises: 20260728_08
Create Date: 2026-07-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260728_09"
down_revision = "20260728_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade únicamente el núcleo Case sin reinterpretar datos existentes."""

    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("retention_mode", sa.String(length=24), nullable=False),
        sa.Column("owner_type", sa.String(length=24), nullable=False),
        sa.Column("owner_key_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("pre_archive_status", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft','active','in_review','closed','archived')", name="ck_cases_status"),
        sa.CheckConstraint("retention_mode IN ('temporary','local_persistent')", name="ck_cases_retention_mode"),
        sa.CheckConstraint("owner_type IN ('guest_session','local_installation','account')", name="ck_cases_owner_type"),
        sa.CheckConstraint(
            "(retention_mode='temporary' AND owner_type='guest_session' AND owner_key_hash IS NOT NULL AND expires_at IS NOT NULL) OR "
            "(retention_mode='local_persistent' AND owner_type='local_installation' AND owner_key_hash IS NULL AND expires_at IS NULL)",
            name="ck_cases_retention_owner",
        ),
        sa.CheckConstraint("version >= 1", name="ck_cases_version"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 200", name="ck_cases_title"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_cases_public_id"),
    )
    op.create_index("ix_cases_owner_access", "cases", ["owner_type", "owner_key_hash", "deleted_at"])
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_retention_mode", "cases", ["retention_mode"])
    op.create_index("ix_cases_expires_at", "cases", ["expires_at"])
    op.create_index("ix_cases_deleted_at", "cases", ["deleted_at"])
    op.create_index("ix_cases_updated_at", "cases", ["updated_at"])

    op.create_table(
        "case_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=True),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("resource_version >= 1", name="ck_case_audit_version"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_audit_case_created", "case_audit_events", ["case_id", "created_at"])


def downgrade() -> None:
    """Retira solo Case y su auditoría; conserva todo el esquema anterior."""

    op.drop_index("ix_case_audit_case_created", table_name="case_audit_events")
    op.drop_table("case_audit_events")
    op.drop_index("ix_cases_updated_at", table_name="cases")
    op.drop_index("ix_cases_deleted_at", table_name="cases")
    op.drop_index("ix_cases_expires_at", table_name="cases")
    op.drop_index("ix_cases_retention_mode", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_owner_access", table_name="cases")
    op.drop_table("cases")
