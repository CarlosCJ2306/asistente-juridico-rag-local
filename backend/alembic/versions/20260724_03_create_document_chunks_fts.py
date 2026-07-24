"""Create the local FTS5 index for document chunks.

Revision ID: 20260724_03
Revises: 20260723_02
Create Date: 2026-07-24 00:00:00
"""

from alembic import op


revision = "20260724_03"
down_revision = "20260723_02"
branch_labels = None
depends_on = None


def _ensure_fts5_available() -> None:
    """Falla antes de crear objetos persistentes cuando SQLite no ofrece FTS5."""

    bind = op.get_bind()
    try:
        bind.exec_driver_sql("CREATE VIRTUAL TABLE temp.__fts5_probe USING fts5(content)")
        bind.exec_driver_sql("DROP TABLE temp.__fts5_probe")
    except Exception as exc:
        raise RuntimeError("FTS5_NOT_AVAILABLE") from exc


def _drop_fts_objects() -> None:
    """Retira de forma idempotente cualquier objeto derivado parcial."""

    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_fts_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_fts_update")
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_fts_insert")
    op.execute("DROP TABLE IF EXISTS document_chunks_fts")


def upgrade() -> None:
    """Crea un índice derivado, sus triggers y el backfill inicial."""

    _ensure_fts5_available()
    try:
        op.execute(
            """
            CREATE VIRTUAL TABLE document_chunks_fts USING fts5(
                text,
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                chunk_index UNINDEXED,
                start_page UNINDEXED,
                end_page UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
        op.execute(
            """
            INSERT INTO document_chunks_fts (
                text, chunk_id, document_id, chunk_index, start_page, end_page
            )
            SELECT c.text, c.id, c.document_id, c.chunk_index, c.start_page, c.end_page
            FROM document_chunks AS c
            JOIN documents AS d ON d.id = c.document_id
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_document_chunks_fts_insert
            AFTER INSERT ON document_chunks
            BEGIN
                INSERT INTO document_chunks_fts (
                    text, chunk_id, document_id, chunk_index, start_page, end_page
                )
                SELECT NEW.text, NEW.id, NEW.document_id, NEW.chunk_index,
                       NEW.start_page, NEW.end_page
                WHERE EXISTS (SELECT 1 FROM documents WHERE id = NEW.document_id);
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_document_chunks_fts_update
            AFTER UPDATE ON document_chunks
            BEGIN
                DELETE FROM document_chunks_fts WHERE chunk_id = OLD.id;
                INSERT INTO document_chunks_fts (
                    text, chunk_id, document_id, chunk_index, start_page, end_page
                )
                SELECT NEW.text, NEW.id, NEW.document_id, NEW.chunk_index,
                       NEW.start_page, NEW.end_page
                WHERE EXISTS (SELECT 1 FROM documents WHERE id = NEW.document_id);
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_document_chunks_fts_delete
            AFTER DELETE ON document_chunks
            BEGIN
                DELETE FROM document_chunks_fts WHERE chunk_id = OLD.id;
            END
            """
        )
    except Exception:
        _drop_fts_objects()
        raise


def downgrade() -> None:
    """Elimina solo el índice derivado y sus triggers."""

    _drop_fts_objects()
