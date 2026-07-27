"""Pruebas temporales de recuperación textual FTS5 sin documentos reales."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.database.models.document import (
    Document,
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    ReviewStatus,
)
from app.database.models.document_chunk import DocumentChunk
from app.database.repositories.text_search_repository import (
    TextSearchRepository,
    TextSearchRepositoryError,
)
from app.database.session import DatabaseSessionManager, get_db_session
from app.services import text_search_service as text_search_service_module
from app.main import app
from app.schemas.text_search import TextMatchMode, TextSearchRequest
from app.services.text_search_service import TextSearchService


@pytest.fixture
def text_search_database(tmp_path: Path):
    from app.core.config import settings

    database_file = tmp_path / "text_search.db"
    previous = settings.database_file
    settings.database_file = database_file
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        settings.database_file = previous
    manager = DatabaseSessionManager(database_file)

    async def populate() -> tuple[UUID, UUID]:
        async with manager.get_session_factory()() as session:
            first = Document(
                original_filename="first.pdf",
                stored_filename="first.pdf",
                relative_path="storage/documents/jurisprudencia/first.pdf",
                document_type=DocumentType.JURISPRUDENCIA,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=1,
                sha256="a" * 64,
                status=DocumentStatus.EXTRACTED,
                index_status=IndexStatus.INDEXED,
            )
            second = Document(
                original_filename="second.pdf",
                stored_filename="second.pdf",
                relative_path="storage/documents/normativa/second.pdf",
                document_type=DocumentType.NORMATIVA,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=1,
                sha256="b" * 64,
                status=DocumentStatus.EXTRACTED,
                index_status=IndexStatus.INDEXED,
            )
            session.add_all([first, second])
            await session.flush()
            session.add_all(
                [
                    DocumentChunk(
                        document_id=first.id, chunk_index=1,
                        text="Garantía del debido proceso constitucional.",
                        char_count=40, word_count=5, start_page=1, end_page=1,
                    ),
                    DocumentChunk(
                        document_id=first.id, chunk_index=2,
                        text="Debido proceso y defensa con tilde: actuación.",
                        char_count=47, word_count=7, start_page=2, end_page=2,
                    ),
                    DocumentChunk(
                        document_id=second.id, chunk_index=1,
                        text="Norma sobre procedimiento administrativo.",
                        char_count=38, word_count=5, start_page=2, end_page=3,
                    ),
                ]
            )
            await session.commit()
            return first.id, second.id

    identifiers = asyncio.run(populate())
    try:
        yield manager, identifiers
    finally:
        asyncio.run(manager.dispose())


def _search(manager: DatabaseSessionManager, request: TextSearchRequest):
    async def run():
        async with manager.get_session_factory()() as session:
            return await TextSearchService(session).search(request)

    return asyncio.run(run())


def test_text_search_modes_unicode_filters_and_pagination(text_search_database) -> None:
    manager, (first_id, _) = text_search_database
    all_terms = _search(manager, TextSearchRequest(query="debido proceso"))
    assert all_terms.total == 2
    assert all(item.document_id == first_id for item in all_terms.items)
    assert all("«" in item.snippet and "»" in item.snippet for item in all_terms.items)
    assert _search(
        manager,
        TextSearchRequest(query="debido norma", match_mode=TextMatchMode.ANY_TERM),
    ).total == 3
    assert _search(
        manager,
        TextSearchRequest(query="debido proceso", match_mode=TextMatchMode.PHRASE),
    ).total == 2
    assert _search(manager, TextSearchRequest(query="actuacion")).total == 1
    filtered = _search(
        manager,
        TextSearchRequest(query="proceso", document_id=first_id, min_page=2, max_page=2),
    )
    assert filtered.total == 1 and filtered.items[0].start_page == 2
    assert _search(
        manager,
        TextSearchRequest(query="procedimiento", min_page=3, max_page=3),
    ).total == 0
    assert _search(manager, TextSearchRequest(query="proceso", page=2, page_size=1)).total == 2
    assert len(_search(manager, TextSearchRequest(query="proceso", page=2, page_size=1)).items) == 1


def test_text_search_triggers_update_delete_and_soft_delete(text_search_database) -> None:
    manager, (first_id, _) = text_search_database

    async def mutate() -> None:
        async with manager.get_session_factory()() as session:
            chunk_id = await session.scalar(text("SELECT id FROM document_chunks WHERE chunk_index = 1 LIMIT 1"))
            await session.execute(
                text("UPDATE document_chunks SET text = :value WHERE id = :chunk_id"),
                {"value": "Actualización exclusiva", "chunk_id": chunk_id},
            )
            await session.commit()
            assert await session.scalar(text("SELECT COUNT(*) FROM document_chunks_fts WHERE chunk_id = :chunk_id"), {"chunk_id": chunk_id}) == 1
            await session.execute(text("UPDATE documents SET is_deleted = 1 WHERE id = :id"), {"id": first_id.hex})
            await session.commit()

    asyncio.run(mutate())
    assert _search(manager, TextSearchRequest(query="actualización")).total == 0


def test_text_search_revalidates_governance_and_layer_filters(
    text_search_database,
) -> None:
    manager, (first_id, second_id) = text_search_database

    async def configure_governance() -> None:
        async with manager.get_session_factory()() as session:
            first = await session.get(Document, first_id)
            second = await session.get(Document, second_id)
            assert first is not None and second is not None
            first.review_status = ReviewStatus.REJECTED
            second.knowledge_layer = KnowledgeLayer.MANAGED_CORPUS
            second.review_status = ReviewStatus.APPROVED
            second.legal_validity_status = LegalValidityStatus.CURRENT

            expired = Document(
                original_filename="expired.pdf",
                stored_filename="expired.pdf",
                relative_path="storage/documents/otros/expired.pdf",
                document_type=DocumentType.OTRO,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=1,
                sha256="c" * 64,
                status=DocumentStatus.EXTRACTED,
                knowledge_layer=KnowledgeLayer.TEMPORARY,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                index_status=IndexStatus.INDEXED,
            )
            candidate = Document(
                original_filename="candidate.pdf",
                stored_filename="candidate.pdf",
                relative_path="storage/documents/otros/candidate.pdf",
                document_type=DocumentType.OTRO,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=1,
                sha256="d" * 64,
                status=DocumentStatus.EXTRACTED,
                knowledge_layer=KnowledgeLayer.GLOBAL_CANDIDATE,
                review_status=ReviewStatus.APPROVED,
                index_status=IndexStatus.INDEXED,
            )
            session.add_all([expired, candidate])
            await session.flush()
            session.add_all(
                [
                    DocumentChunk(
                        document_id=expired.id,
                        chunk_index=1,
                        text="marcador gobernado temporal",
                        char_count=27,
                        word_count=3,
                        start_page=1,
                        end_page=1,
                    ),
                    DocumentChunk(
                        document_id=candidate.id,
                        chunk_index=1,
                        text="marcador gobernado candidato",
                        char_count=28,
                        word_count=3,
                        start_page=1,
                        end_page=1,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(configure_governance())
    assert _search(
        manager,
        TextSearchRequest(query="debido", document_id=first_id),
    ).total == 0
    managed = _search(
        manager,
        TextSearchRequest(
            query="procedimiento",
            knowledge_layers=[
                KnowledgeLayer.MANAGED_CORPUS,
                KnowledgeLayer.MANAGED_CORPUS,
            ],
        ),
    )
    assert managed.total == 1
    assert managed.items[0].document_id == second_id
    assert managed.items[0].knowledge_layer is KnowledgeLayer.MANAGED_CORPUS
    assert _search(manager, TextSearchRequest(query="temporal")).total == 0
    assert _search(manager, TextSearchRequest(query="candidato")).total == 0


def test_text_search_compiler_rejects_controls_and_never_interprets_operators(text_search_database) -> None:
    manager, _ = text_search_database
    malicious_inputs = [
        "OR", "AND", "NOT", "NEAR", "texto*", "chunk_text:secreto",
        '"texto"', 'texto") OR ("otro', "'); DROP TABLE documents; --",
    ]
    for query in malicious_inputs:
        assert _search(manager, TextSearchRequest(query=query)).total == 0
    with pytest.raises(ValidationError, match="caracteres de control"):
        TextSearchRequest(query="consulta\x00invalida")
    normalized, terms = TextSearchService._normalize_query("debido    proceso")
    assert normalized == "debido proceso"
    assert TextSearchService._compile_match_expression(
        normalized, terms, TextMatchMode.ALL_TERMS
    ) == '"debido" AND "proceso"'


def test_text_search_logs_only_operational_metadata(
    text_search_database,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _ = text_search_database

    def capture(message: str, **context) -> None:
        logging.getLogger("text_search_audit").info("%s %s", message, context)

    monkeypatch.setattr(text_search_service_module, "log_info", capture)
    monkeypatch.setattr(text_search_service_module, "log_success", capture)
    with caplog.at_level(logging.INFO, logger="text_search_audit"):
        _search(manager, TextSearchRequest(query="MARCADOR_SINTETICO_PRIVADO"))
    assert "MARCADOR_SINTETICO_PRIVADO" not in caplog.text
    assert "match_expression" not in caplog.text
    assert "query_length" in caplog.text


def test_text_search_snippet_escapes_synthetic_html(text_search_database) -> None:
    manager, (first_id, _) = text_search_database

    async def insert_html() -> None:
        async with manager.get_session_factory()() as session:
            session.add(
                DocumentChunk(
                    document_id=first_id,
                    chunk_index=3,
                    text="<script>alert(1)</script> marcadorhtml",
                    char_count=42,
                    word_count=2,
                    start_page=4,
                    end_page=4,
                )
            )
            await session.commit()

    asyncio.run(insert_html())
    item = _search(manager, TextSearchRequest(query="marcadorhtml")).items[0]
    assert "<script>" not in item.snippet
    assert "&lt;script&gt;" in item.snippet
    assert len(item.snippet) <= 500


def test_text_search_api_and_index_not_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DatabaseSessionManager(tmp_path / "empty.db")

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post("/api/search/text", json={"query": "consulta"})
        assert response.status_code == 503
        assert response.json()["detail"] == "TEXT_SEARCH_INDEX_NOT_READY"
        assert "consulta" not in response.text
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def test_text_search_api_returns_typed_results_empty_page_and_422(text_search_database) -> None:
    manager, _ = text_search_database

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            found = client.post("/api/search/text", json={"query": "debido proceso"})
            empty = client.post("/api/search/text", json={"query": "inexistente"})
            invalid = client.post("/api/search/text", json={"query": "   "})
        assert found.status_code == 200 and found.json()["total"] == 2
        assert empty.status_code == 200 and empty.json()["items"] == []
        assert invalid.status_code == 422
        serialized = found.text.lower()
        for forbidden in ("debido proceso", "match_expression", "relative_path", "sha256"):
            assert forbidden not in serialized
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def test_text_search_api_maps_missing_fts5_to_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseSessionManager(tmp_path / "fts_missing.db")

    async def unavailable(_self) -> None:
        raise TextSearchRepositoryError("FTS5_NOT_AVAILABLE")

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(TextSearchRepository, "_ensure_index_ready", unavailable)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post("/api/search/text", json={"query": "sintético"})
        assert response.status_code == 503
        assert response.json() == {"detail": "FTS5_NOT_AVAILABLE"}
        assert "sintético" not in response.text
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())
