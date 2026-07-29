"""Pruebas de la cadena Alembic con datos exclusivamente temporales."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import settings


def _run_migration(database_file: Path, revision: str) -> None:
    previous = settings.database_file
    settings.database_file = database_file
    try:
        command.upgrade(Config("alembic.ini"), revision)
    finally:
        settings.database_file = previous


def _downgrade_migration(database_file: Path, revision: str) -> None:
    previous = settings.database_file
    settings.database_file = database_file
    try:
        command.downgrade(Config("alembic.ini"), revision)
    finally:
        settings.database_file = previous


def _document_row(status: str = "registered") -> tuple[str, tuple[object, ...]]:
    document_id = uuid4().hex
    values = (
        document_id,
        "original.pdf",
        "stored.pdf",
        f"storage/documents/otros/{document_id}.pdf",
        "otro",
        "application/pdf",
        ".pdf",
        12,
        uuid4().hex * 2,
        status,
        None,
        None,
        "2026-07-23 00:00:00",
        "2026-07-23 00:00:00",
        None,
        0,
    )
    return document_id, values


def test_migration_upgrade_downgrade_preserves_documents_and_normalizes_states(tmp_path: Path) -> None:
    database_file = tmp_path / "migration.db"
    _run_migration(database_file, "20260723_01")
    first_id, first_values = _document_row()
    second_id, second_values = _document_row()
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", first_values
        )
        connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", second_values
        )
        connection.commit()

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "UPDATE documents SET status='extracted' WHERE id=?", (first_id,)
        )
        connection.execute(
            "UPDATE documents SET status='extraction_failed' WHERE id=?", (second_id,)
        )
        connection.execute(
            "INSERT INTO document_pages VALUES (?,?,?,?,?,?)",
            (uuid4().hex, first_id, 1, "Página", 6, "2026-07-23 00:00:00"),
        )
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (uuid4().hex, first_id, 1, "Chunk", 5, 1, 1, 1, "2026-07-23 00:00:00"),
        )
        connection.commit()
        assert connection.execute(
            "SELECT COUNT(*) FROM document_pages WHERE document_id=?", (first_id,)
        ).fetchone()[0] == 1

        page_constraints = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='document_pages'"
        ).fetchone()[0]
        chunk_constraints = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='document_chunks'"
        ).fetchone()[0]
        for constraint in (
            "ck_document_pages_page_number_positive",
            "ck_document_pages_char_count_nonnegative",
        ):
            assert constraint in page_constraints
        for constraint in (
            "ck_document_chunks_index_positive",
            "ck_document_chunks_char_count_nonnegative",
            "ck_document_chunks_word_count_nonnegative",
            "ck_document_chunks_start_page_positive",
            "ck_document_chunks_end_page_positive",
            "ck_document_chunks_page_range",
        ):
            assert constraint in chunk_constraints

        invalid_page = (uuid4().hex, first_id, 0, "", 0, "2026-07-23 00:00:00")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO document_pages VALUES (?,?,?,?,?,?)", invalid_page)
            connection.rollback()
        invalid_chunk = (uuid4().hex, first_id, 0, "", -1, -1, 0, 1, "2026-07-23 00:00:00")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)", invalid_chunk)
            connection.rollback()

    _downgrade_migration(database_file, "20260723_01")
    with sqlite3.connect(database_file) as connection:
        rows = connection.execute("SELECT * FROM documents ORDER BY id").fetchall()
        assert {row[0] for row in rows} == {first_id, second_id}
        assert {row[1] for row in rows} == {"original.pdf"}
        assert {row[3].startswith("storage/documents/otros/") for row in rows} == {True}
        expected_by_id = {
            first_id: (*first_values[:9], "pending_extraction", *first_values[10:]),
            second_id: (*second_values[:9], "failed", *second_values[10:]),
        }
        for row in rows:
            expected = expected_by_id[row[0]]
            assert row == expected
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='document_pages'"
        ).fetchone() is None
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list('documents')").fetchall()
        }
        assert "ix_documents_sha256" in indexes
        assert "ix_documents_status" in indexes
        document_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'"
        ).fetchone()[0]
        assert "uq_documents_relative_path" in document_sql


def test_fts5_migration_backfills_synchronizes_and_downgrades(tmp_path: Path) -> None:
    database_file = tmp_path / "fts.db"
    _run_migration(database_file, "20260723_02")
    document_id, values = _document_row(status="extracted")
    chunk_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (chunk_id, document_id, 1, "Garantía con tilde", 19, 3, 1, 1, "2026-07-24 00:00:00"),
        )
        connection.commit()

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts WHERE document_chunks_fts MATCH 'garantia'").fetchone()[0] == 1
        triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        assert {
            "trg_document_chunks_fts_insert",
            "trg_document_chunks_fts_update",
            "trg_document_chunks_fts_delete",
        } <= triggers
        connection.execute("UPDATE document_chunks SET text='Actualizado' WHERE id=?", (chunk_id,))
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts WHERE document_chunks_fts MATCH 'actualizado'").fetchone()[0] == 1
        connection.execute(
            "UPDATE document_chunks SET text='Segunda versión', chunk_index=2, "
            "start_page=2, end_page=3 WHERE id=?",
            (chunk_id,),
        )
        connection.commit()
        indexed = connection.execute(
            "SELECT chunk_index, start_page, end_page FROM document_chunks_fts "
            "WHERE chunk_id=?",
            (chunk_id,),
        ).fetchall()
        assert indexed == [(2, 2, 3)]
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks_fts WHERE chunk_id=?", (chunk_id,)
        ).fetchone()[0] == 1
        connection.execute("DELETE FROM document_chunks WHERE id=?", (chunk_id,))
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 0

    _downgrade_migration(database_file, "20260723_02")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='document_chunks_fts'").fetchone() is None
        assert connection.execute("SELECT COUNT(*) FROM documents WHERE id=?", (document_id,)).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 0


def test_fts5_triggers_handle_document_change_and_cascade_without_duplicates(tmp_path: Path) -> None:
    database_file = tmp_path / "fts_cascade.db"
    _run_migration(database_file, "20260723_02")
    first_id, first_values = _document_row(status="extracted")
    second_id, second_values = _document_row(status="extracted")
    first_chunk = uuid4().hex
    second_chunk = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", first_values)
        connection.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", second_values)
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (first_chunk, first_id, 1, "Primero", 7, 1, 1, 1, "2026-07-24 00:00:00"),
        )
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (second_chunk, second_id, 1, "Segundo", 7, 1, 1, 1, "2026-07-24 00:00:00"),
        )
        connection.commit()
    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 2
        connection.execute(
            "UPDATE document_chunks SET document_id=?, chunk_index=2, "
            "text='Movido', start_page=4, end_page=5 WHERE id=?",
            (second_id, first_chunk),
        )
        connection.commit()
        moved = connection.execute(
            "SELECT document_id, chunk_index, start_page, end_page "
            "FROM document_chunks_fts WHERE chunk_id=?",
            (first_chunk,),
        ).fetchall()
        assert moved == [(second_id, 2, 4, 5)]
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks_fts WHERE chunk_id=?", (first_chunk,)
        ).fetchone()[0] == 1
        connection.execute("DELETE FROM documents WHERE id=?", (second_id,))
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM documents WHERE id=?", (first_id,)).fetchone()[0] == 1


def test_document_governance_migration_round_trip_is_additive(tmp_path: Path) -> None:
    database_file = tmp_path / "document_governance.db"
    _run_migration(database_file, "20260725_04")
    document_id, values = _document_row(status="extracted")
    chunk_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (
                chunk_id,
                document_id,
                1,
                "Contenido sintético",
                19,
                2,
                1,
                1,
                "2026-07-26 00:00:00",
            ),
        )
        connection.commit()

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        row = connection.execute(
            "SELECT display_name, knowledge_layer, source_kind, review_status, "
            "legal_validity_status, index_status, status, sha256, relative_path "
            "FROM documents WHERE id=?",
            (document_id,),
        ).fetchone()
        assert row == (
            "original.pdf",
            "private_library",
            "local_upload",
            "not_required",
            "unknown",
            "not_requested",
            "extracted",
            values[8],
            values[3],
        )
        columns = {
            item[1]: item for item in connection.execute("PRAGMA table_info('documents')")
        }
        assert columns["display_name"][3] == 1
        assert columns["knowledge_layer"][3] == 1
        indexes = {
            item[1] for item in connection.execute("PRAGMA index_list('documents')")
        }
        assert {
            "ix_documents_knowledge_layer_deleted",
            "ix_documents_review_status",
            "ix_documents_legal_validity_status",
            "ix_documents_index_status",
            "ix_documents_expires_at",
            "ix_documents_supersedes_document_id",
        } <= indexes
        foreign_keys = connection.execute("PRAGMA foreign_key_list('documents')").fetchall()
        assert any(
            item[2] == "documents"
            and item[3] == "supersedes_document_id"
            and item[4] == "id"
            for item in foreign_keys
        )
        replacement_id = uuid4().hex
        connection.execute(
            "INSERT INTO documents ("
            "id, original_filename, stored_filename, relative_path, document_type, "
            "mime_type, extension, size_bytes, sha256, status, error_code, error_message, "
            "created_at, updated_at, deleted_at, is_deleted, display_name, "
            "supersedes_document_id"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                replacement_id,
                "replacement.pdf",
                "replacement.pdf",
                "storage/documents/otros/replacement.pdf",
                "otro",
                "application/pdf",
                ".pdf",
                10,
                "f" * 64,
                "registered",
                None,
                None,
                "2026-07-26 00:00:00",
                "2026-07-26 00:00:00",
                None,
                0,
                "Versión nueva",
                document_id,
            ),
        )
        connection.commit()
        assert connection.execute(
            "SELECT supersedes_document_id FROM documents WHERE id=?",
            (replacement_id,),
        ).fetchone()[0] == document_id
        with pytest.raises(sqlite3.IntegrityError, match="DOCUMENT_SUPERSEDES_SELF"):
            connection.execute(
                "UPDATE documents SET supersedes_document_id=id WHERE id=?",
                (document_id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE documents SET knowledge_layer='invalid' WHERE id=?",
                (document_id,),
            )
        connection.rollback()
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks_fts WHERE chunk_id=?",
            (chunk_id,),
        ).fetchone()[0] == 1

    _downgrade_migration(database_file, "20260725_04")
    with sqlite3.connect(database_file) as connection:
        columns = {
            item[1] for item in connection.execute("PRAGMA table_info('documents')")
        }
        assert "knowledge_layer" not in columns
        assert "supersedes_document_id" not in columns
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 1

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute(
            "SELECT display_name, knowledge_layer FROM documents WHERE id=?",
            (document_id,),
        ).fetchone() == ("original.pdf", "private_library")
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 1


def test_managed_corpus_registry_migration_is_reversible_and_additive(
    tmp_path: Path,
) -> None:
    database_file = tmp_path / "managed_corpus_registry.db"
    _run_migration(database_file, "20260726_05")
    document_id, values = _document_row(status="registered")
    with sqlite3.connect(database_file) as connection:
        connection.execute(
            "INSERT INTO documents ("
            "id, original_filename, stored_filename, relative_path, document_type, "
            "mime_type, extension, size_bytes, sha256, status, error_code, error_message, "
            "created_at, updated_at, deleted_at, is_deleted"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )
        connection.commit()

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO managed_corpus_entries "
            "(corpus_id, source_key, document_id, imported_at) VALUES (?,?,?,?)",
            ("test-corpus", "source-v1", document_id, "2026-07-27 00:00:00"),
        )
        connection.commit()
        assert connection.execute(
            "SELECT document_id FROM managed_corpus_entries "
            "WHERE corpus_id=? AND source_key=?",
            ("test-corpus", "source-v1"),
        ).fetchone() == (document_id,)

    _downgrade_migration(database_file, "20260726_05")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='managed_corpus_entries'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT COUNT(*) FROM documents WHERE id=?", (document_id,)
        ).fetchone()[0] == 1

def test_document_processing_queue_migration_is_additive_and_reversible(
    tmp_path: Path,
) -> None:
    database_file = tmp_path / "document_processing_queue.db"
    _run_migration(database_file, "20260727_06")
    document_id, values = _document_row(status="registered")
    with sqlite3.connect(database_file) as connection:
        connection.execute(
            "INSERT INTO documents ("
            "id, original_filename, stored_filename, relative_path, document_type, "
            "mime_type, extension, size_bytes, sha256, status, error_code, error_message, "
            "created_at, updated_at, deleted_at, is_deleted"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )
        connection.commit()

    _run_migration(database_file, "20260728_07")
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO document_processing_jobs ("
            "id, document_id, knowledge_layer, public_name, operation, state, "
            "attempts, created_at, updated_at"
            ") VALUES (?,?,?,?,?,?,?,?,?)",
            (
                uuid4().hex,
                document_id,
                "private_library",
                "Documento sintético",
                "upload_pipeline",
                "queued",
                0,
                "2026-07-28 00:00:00",
                "2026-07-28 00:00:00",
            ),
        )
        connection.commit()
        assert connection.execute(
            "SELECT COUNT(*) FROM document_processing_jobs"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM documents WHERE id=?", (document_id,)
        ).fetchone()[0] == 1

    _downgrade_migration(database_file, "20260727_06")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='document_processing_jobs'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT COUNT(*) FROM documents WHERE id=?", (document_id,)
        ).fetchone()[0] == 1


def test_conversation_migration_is_additive_cascading_and_reversible(
    tmp_path: Path,
) -> None:
    database_file = tmp_path / "conversations.db"
    _run_migration(database_file, "20260728_07")
    with sqlite3.connect(database_file) as connection:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    _run_migration(database_file, "20260728_08")
    conversation_id = uuid4().hex
    message_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "conversations",
            "conversation_messages",
            "conversation_citations",
            "conversation_claims",
            "conversation_claim_citations",
        } <= tables
        connection.execute(
            "INSERT INTO conversations ("
            "id,title,owner_type,guest_session_hash,status,created_at,updated_at,"
            "last_activity_at,expires_at,schema_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                conversation_id,
                "Conversación sintética",
                "guest",
                "a" * 64,
                "active",
                "2026-07-28 00:00:00",
                "2026-07-28 00:00:00",
                "2026-07-28 00:00:00",
                "2026-08-04 00:00:00",
                1,
            ),
        )
        connection.execute(
            "INSERT INTO conversation_messages ("
            "id,conversation_id,role,content,sequence_number,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                message_id,
                conversation_id,
                "user",
                "Pregunta sintética",
                1,
                "2026-07-28 00:00:00",
            ),
        )
        connection.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        assert connection.execute(
            "SELECT COUNT(*) FROM conversation_messages"
        ).fetchone()[0] == 0
        connection.commit()

    _downgrade_migration(database_file, "20260728_07")
    with sqlite3.connect(database_file) as connection:
        remaining_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert not any(name.startswith("conversation") for name in remaining_tables)
    assert existing_tables <= remaining_tables


def test_case_migration_is_additive_constrained_and_reversible(tmp_path: Path) -> None:
    database_file = tmp_path / "cases.db"
    _run_migration(database_file, "20260728_08")
    with sqlite3.connect(database_file) as connection:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    _run_migration(database_file, "20260728_09")
    case_id = uuid4().hex
    public_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"cases", "case_audit_events"} <= tables
        connection.execute(
            "INSERT INTO cases (id,public_id,title,status,retention_mode,owner_type,"
            "last_activity_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                case_id,
                public_id,
                "Caso sintético",
                "draft",
                "local_persistent",
                "local_installation",
                "2026-07-28 00:00:00",
                1,
                "2026-07-28 00:00:00",
                "2026-07-28 00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO case_audit_events "
            "(id,case_id,event_type,actor_type,to_status,resource_version,result_code,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                uuid4().hex,
                case_id,
                "created",
                "local_installation",
                "draft",
                1,
                "CASE_OPERATION_COMPLETED",
                "2026-07-28 00:00:00",
            ),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cases (id,public_id,title,status,retention_mode,owner_type,"
                "last_activity_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    uuid4().hex,
                    "Inválido",
                    "draft",
                    "temporary",
                    "guest_session",
                    "2026-07-28 00:00:00",
                    1,
                    "2026-07-28 00:00:00",
                    "2026-07-28 00:00:00",
                ),
            )
        connection.commit()

    _downgrade_migration(database_file, "20260728_08")
    with sqlite3.connect(database_file) as connection:
        remaining_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "cases" not in remaining_tables
    assert "case_audit_events" not in remaining_tables
    assert existing_tables <= remaining_tables

    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0] == 0


def test_case_document_migration_is_partial_unique_and_reversible(tmp_path: Path) -> None:
    database_file = tmp_path / "case-documents.db"
    _run_migration(database_file, "20260728_09")
    case_id = uuid4().hex
    document_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        connection.execute(
            "INSERT INTO cases (id,public_id,title,status,retention_mode,owner_type,"
            "last_activity_at,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                case_id,
                uuid4().hex,
                "Caso sintético",
                "draft",
                "local_persistent",
                "local_installation",
                "2026-07-29 00:00:00",
                1,
                "2026-07-29 00:00:00",
                "2026-07-29 00:00:00",
            ),
        )
        connection.execute(
            "INSERT INTO documents (id,original_filename,display_name,stored_filename,"
            "relative_path,document_type,mime_type,extension,size_bytes,sha256,status,"
            "knowledge_layer,source_kind,review_status,legal_validity_status,index_status,"
            "created_at,updated_at,is_deleted) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                document_id,
                "synthetic.pdf",
                "Documento sintético",
                "synthetic.pdf",
                "storage/documents/otros/synthetic.pdf",
                "expediente",
                "application/pdf",
                ".pdf",
                10,
                uuid4().hex + uuid4().hex,
                "extracted",
                "private_library",
                "local_upload",
                "not_required",
                "unknown",
                "indexed",
                "2026-07-29 00:00:00",
                "2026-07-29 00:00:00",
                0,
            ),
        )
        connection.commit()

    _run_migration(database_file, "20260729_10")
    columns = (
        "id,public_id,case_id,document_id,purpose,display_order,"
        "snapshot_display_name,snapshot_document_type,snapshot_knowledge_layer,"
        "snapshot_source_kind,snapshot_review_status,snapshot_legal_validity_status,"
        "snapshot_extraction_status,snapshot_index_status,snapshot_document_updated_at,"
        "version,attached_at,updated_at"
    )

    def values(link_id: str, public_id: str, *, order: int = 0) -> tuple[object, ...]:
        return (
            link_id,
            public_id,
            case_id,
            document_id,
            "primary_record",
            order,
            "Documento sintético",
            "expediente",
            "private_library",
            "local_upload",
            "not_required",
            "unknown",
            "extracted",
            "indexed",
            "2026-07-29 00:00:00",
            1,
            "2026-07-29 00:00:00",
            "2026-07-29 00:00:00",
        )

    first_id = uuid4().hex
    with sqlite3.connect(database_file) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        indexes = {
            row[1]: row
            for row in connection.execute("PRAGMA index_list('case_documents')")
        }
        assert indexes["uq_case_documents_active_case_document"][2] == 1
        assert indexes["uq_case_documents_active_case_document"][4] == 1
        connection.execute(
            f"INSERT INTO case_documents ({columns}) VALUES ({','.join('?' * 18)})",
            values(first_id, uuid4().hex),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"INSERT INTO case_documents ({columns}) VALUES ({','.join('?' * 18)})",
                values(uuid4().hex, uuid4().hex),
            )
        connection.rollback()
        connection.execute(
            "UPDATE case_documents SET removed_at=?,updated_at=? WHERE id=?",
            ("2026-07-29 00:01:00", "2026-07-29 00:01:00", first_id),
        )
        connection.execute(
            f"INSERT INTO case_documents ({columns}) VALUES ({','.join('?' * 18)})",
            values(uuid4().hex, uuid4().hex, order=1),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            invalid = list(values(uuid4().hex, uuid4().hex))
            invalid[5] = -1
            connection.execute(
                f"INSERT INTO case_documents ({columns}) VALUES ({','.join('?' * 18)})",
                tuple(invalid),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            orphan = list(values(uuid4().hex, uuid4().hex))
            orphan[2] = uuid4().hex
            connection.execute(
                f"INSERT INTO case_documents ({columns}) VALUES ({','.join('?' * 18)})",
                tuple(orphan),
            )
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1

    _downgrade_migration(database_file, "20260728_09")
    with sqlite3.connect(database_file) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "case_documents" not in tables
        assert existing_tables <= tables
        assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    _run_migration(database_file, "head")
    with sqlite3.connect(database_file) as connection:
        assert connection.execute("SELECT COUNT(*) FROM case_documents").fetchone()[0] == 0
