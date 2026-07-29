"""Migración y restricciones HPN sobre SQLite temporal."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.database.session import DatabaseSessionManager


def _migrate(database: Path, revision: str) -> None:
    previous = settings.database_file
    settings.database_file = database
    try:
        command.upgrade(Config("alembic.ini"), revision)
    finally:
        settings.database_file = previous


def _downgrade(database: Path, revision: str) -> None:
    previous = settings.database_file
    settings.database_file = database
    try:
        command.downgrade(Config("alembic.ini"), revision)
    finally:
        settings.database_file = previous


def test_hpn_migration_chain_constraints_and_safe_downgrade(tmp_path: Path) -> None:
    database = tmp_path / "hpn_migration.db"
    _migrate(database, "20260724_03")
    document_id = uuid4().hex
    chunk_id = uuid4().hex
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO documents (id, original_filename, stored_filename, relative_path, "
            "document_type, mime_type, extension, size_bytes, sha256, status, error_code, "
            "error_message, created_at, updated_at, deleted_at, is_deleted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                document_id,
                "source.pdf",
                "stored.pdf",
                "storage/documents/otros/stored.pdf",
                "otro",
                "application/pdf",
                ".pdf",
                1,
                "a" * 64,
                "extracted",
                None,
                None,
                "2026-07-25 00:00:00",
                "2026-07-25 00:00:00",
                None,
                0,
            ),
        )
        connection.execute(
            "INSERT INTO document_chunks VALUES (?,?,?,?,?,?,?,?,?)",
            (chunk_id, document_id, 1, "synthetic", 9, 1, 1, 1, "2026-07-25 00:00:00"),
        )
        connection.commit()
    with pytest.warns(DeprecationWarning, match="path_separator"):
        _migrate(database, "head")
    with sqlite3.connect(database) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert {"hpn_matrices", "hpn_nodes", "hpn_node_sources", "hpn_relations"} <= tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260728_08"
        foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute("PRAGMA foreign_key_list('hpn_node_sources')")
        }
        assert ("hpn_nodes", "node_id", "id") in foreign_keys
        assert ("documents", "document_id", "id") in foreign_keys
        assert ("document_chunks", "chunk_id", "id") in foreign_keys
        matrix_id, node_id = uuid4().hex, uuid4().hex
        connection.execute(
            "INSERT INTO hpn_matrices VALUES (?,?,?,?,?,?,?)",
            (matrix_id, "M", None, "draft", "2026-07-25", "2026-07-25", None),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO hpn_nodes VALUES (?,?,?,?,?,?,?,?,?,?)",
                (node_id, matrix_id, "fact", "T", "S", "draft", 0, "2026-07-25", "2026-07-25", None),
            )
        connection.rollback()
        connection.execute(
            "INSERT INTO hpn_matrices VALUES (?,?,?,?,?,?,?)",
            (matrix_id, "M", None, "draft", "2026-07-25", "2026-07-25", None),
        )
        for invalid_node_type, invalid_review in (("free", "draft"), ("fact", "free")):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO hpn_nodes VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        uuid4().hex,
                        matrix_id,
                        invalid_node_type,
                        "T",
                        "S",
                        invalid_review,
                        1,
                        "2026-07-25",
                        "2026-07-25",
                        None,
                    ),
                )
            connection.rollback()
            connection.execute(
                "INSERT OR IGNORE INTO hpn_matrices VALUES (?,?,?,?,?,?,?)",
                (matrix_id, "M", None, "draft", "2026-07-25", "2026-07-25", None),
            )
        indexes = {row[1] for row in connection.execute("PRAGMA index_list('hpn_relations')")}
        assert "uq_hpn_relations_active" in indexes
        source_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list('hpn_node_sources')")
        }
        assert "uq_hpn_node_sources_active_chunk" in source_indexes
        assert "ix_hpn_node_sources_chunk_id" in source_indexes
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE 'trg_hpn_node_sources_owner_%'"
            )
        }
        assert triggers == {
            "trg_hpn_node_sources_owner_insert",
            "trg_hpn_node_sources_owner_update",
        }

        owner_matrix_id = uuid4().hex
        owner_node_id = uuid4().hex
        other_document_id = uuid4().hex
        connection.execute(
            "INSERT INTO hpn_matrices VALUES (?,?,?,?,?,?,?)",
            (
                owner_matrix_id,
                "Ownership",
                None,
                "draft",
                "2026-07-25",
                "2026-07-25",
                None,
            ),
        )
        connection.execute(
            "INSERT INTO hpn_nodes VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                owner_node_id,
                owner_matrix_id,
                "evidence",
                "T",
                "S",
                "draft",
                1,
                "2026-07-25",
                "2026-07-25",
                None,
            ),
        )
        connection.execute(
            "INSERT INTO documents (id, original_filename, stored_filename, relative_path, "
            "document_type, mime_type, extension, size_bytes, sha256, status, error_code, "
            "error_message, created_at, updated_at, deleted_at, is_deleted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                other_document_id,
                "other.pdf",
                "other-stored.pdf",
                "storage/documents/otros/other-stored.pdf",
                "otro",
                "application/pdf",
                ".pdf",
                1,
                "b" * 64,
                "extracted",
                None,
                None,
                "2026-07-25 00:00:00",
                "2026-07-25 00:00:00",
                None,
                0,
            ),
        )
        connection.commit()
        source_values = (
            uuid4().hex,
            owner_node_id,
            chunk_id,
            other_document_id,
            "source.pdf",
            "otro",
            1,
            1,
            1,
            "c" * 64,
            "2026-07-25",
            "2026-07-25",
            None,
        )
        with pytest.raises(sqlite3.IntegrityError, match="HPN_SOURCE_DOCUMENT_CHUNK_MISMATCH"):
            connection.execute(
                "INSERT INTO hpn_node_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                source_values,
            )
        connection.rollback()
        valid_source_id = uuid4().hex
        connection.execute(
            "INSERT INTO hpn_node_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (valid_source_id, *source_values[1:3], document_id, *source_values[4:]),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="HPN_SOURCE_DOCUMENT_CHUNK_MISMATCH"):
            connection.execute(
                "UPDATE hpn_node_sources SET document_id=? WHERE id=?",
                (other_document_id, valid_source_id),
            )
        connection.rollback()
    _downgrade(database, "20260724_03")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM document_chunks_fts").fetchone()[0] == 1
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='hpn_matrices'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'trg_hpn_node_sources_owner_%'"
        ).fetchone() is None
    _migrate(database, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260728_08"
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0] == 1


def test_hpn_revision_remains_in_single_linear_migration_chain() -> None:
    migration = Path("alembic/versions/20260725_04_create_hpn_matrix.py").read_text(
        encoding="utf-8"
    )
    assert 'revision = "20260725_04"' in migration
    assert 'down_revision = "20260724_03"' in migration
    versions = Path("alembic/versions")
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in versions.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            if line.startswith("revision = "):
                revisions.add(line.split('"')[1])
            elif line.startswith("down_revision = ") and "None" not in line:
                parents.add(line.split('"')[1])
    assert revisions - parents == {"20260728_08"}


def test_database_manager_enables_sqlite_foreign_keys(tmp_path: Path) -> None:
    manager = DatabaseSessionManager(tmp_path / "foreign_keys.db")

    async def probe() -> int:
        async with manager.get_engine().connect() as connection:
            result = await connection.exec_driver_sql("PRAGMA foreign_keys")
            value = int(result.scalar_one())
        await manager.dispose()
        return value

    assert asyncio.run(probe()) == 1
