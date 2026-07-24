"""Pruebas de extracción local con PDFs sintéticos y almacenamiento temporal."""

from __future__ import annotations

import asyncio
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as document_routes
from app.database.base import Base
from app.database.models.document import Document, DocumentStatus, DocumentType
from app.database.session import DatabaseSessionManager, get_db_session
from app.ingestion.legal_chunker import CleanPage, chunk_pages
from app.ingestion.pdf_reader import PdfReadError, read_pdf_pages, resolve_document_path
from app.ingestion.text_cleaner import clean_text
from app.main import app
from app.services.document_extraction_service import DocumentExtractionService


def _create_pdf(path: Path, pages: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with fitz.open() as pdf:
        for text in pages:
            page = pdf.new_page()
            if text:
                page.insert_text((72, 72), text)
        pdf.save(path)


@pytest.fixture
def extraction_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project_root = tmp_path
    database_file = project_root / "storage" / "database" / "documents.db"
    database_file.parent.mkdir(parents=True)
    manager = DatabaseSessionManager(database_file)

    async def create_schema() -> None:
        async with manager.get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    documents_directory = project_root / "storage" / "documents"

    def extraction_factory(session):
        return DocumentExtractionService(
            session,
            documents_directory=documents_directory,
            project_root=project_root,
            minimum_extractable_chars=5,
            target_chunk_chars=60,
            maximum_chunk_chars=90,
            overlap_chunk_chars=10,
        )

    async def override_session():
        async with manager.get_session_factory()() as session:
            yield session

    monkeypatch.setattr(document_routes, "_extraction_service", extraction_factory)
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, project_root, manager
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(manager.dispose())


def _register_document(project_root: Path, manager: DatabaseSessionManager, pages: list[str]) -> Document:
    path = project_root / "storage" / "documents" / "jurisprudencia" / "synthetic.pdf"
    _create_pdf(path, pages)

    async def create() -> Document:
        async with manager.get_session_factory()() as session:
            document = Document(
                original_filename="synthetic.pdf",
                stored_filename="synthetic.pdf",
                relative_path="storage/documents/jurisprudencia/synthetic.pdf",
                document_type=DocumentType.JURISPRUDENCIA,
                mime_type="application/pdf",
                extension=".pdf",
                size_bytes=path.stat().st_size,
                sha256="a" * 64,
                status=DocumentStatus.PENDING_EXTRACTION,
            )
            session.add(document)
            await session.commit()
            return document

    return asyncio.run(create())


def test_pdf_reader_preserves_order_and_empty_page(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    _create_pdf(path, ["Primera página", "", "Tercera página"])

    pages = read_pdf_pages(path)

    assert [page.page_number for page in pages] == [1, 2, 3]
    assert pages[0].raw_text.startswith("Primera")
    assert pages[1].raw_text == ""


def test_pdf_reader_reconstructs_visual_words_lines_and_blocks(tmp_path: Path) -> None:
    path = tmp_path / "layout.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "ENCABEZADO")
        page.insert_text((72, 96), "motel")
        page.insert_text((112, 96), '"Cancún",')
        page.insert_text((172, 96), "hora")
        page.insert_text((202, 96), "y lugar")
        page.insert_text((72, 120), "Radicación 123-456. Señor Peña.")
        page.insert_text((72, 165), "Segundo párrafo con actuación ocurrida.")
        pdf.save(path)

    text = read_pdf_pages(path)[0].raw_text

    assert 'motel "Cancún", hora y lugar' in text
    assert "Radicación 123-456. Señor Peña." in text
    assert "ENCABEZADO" in text
    assert "\n" in text
    assert read_pdf_pages(path)[0].raw_text == text


def test_pdf_reader_rejects_invalid_paths_and_corrupt_pdf(tmp_path: Path) -> None:
    documents = tmp_path / "storage" / "documents"
    with pytest.raises(PdfReadError, match="PDF_PATH_INVALID"):
        resolve_document_path("../outside.pdf", documents_directory=documents, project_root=tmp_path)
    with pytest.raises(PdfReadError, match="PDF_FILE_NOT_FOUND"):
        resolve_document_path("storage/documents/missing.pdf", documents_directory=documents, project_root=tmp_path)
    corrupt = documents / "other" / "corrupt.pdf"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"not a PDF")
    with pytest.raises(PdfReadError, match="PDF_UNREADABLE"):
        read_pdf_pages(corrupt)


def test_pdf_reader_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Texto protegido")
        pdf.save(
            path,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )

    with pytest.raises(PdfReadError, match="PDF_ENCRYPTED"):
        read_pdf_pages(path)


def test_text_cleaner_is_conservative_and_deterministic() -> None:
    raw = "Artículo 1.º  Radicación  123-456\x00\r\n\r\n\r\nSeñor  Pérez"
    cleaned = clean_text(raw)

    assert cleaned == "Artículo 1.º Radicación 123-456\n\nSeñor Pérez"
    assert clean_text(raw) == cleaned


def test_legal_chunker_preserves_limits_pages_and_determinism() -> None:
    pages = [
        CleanPage(1, "Artículo primero. " * 8),
        CleanPage(2, "Artículo segundo. " * 8),
    ]
    chunks = chunk_pages(pages, target_size=60, maximum_size=90, overlap_size=10)

    assert chunks[0].chunk_index == 1
    assert all(chunk.text and chunk.char_count <= 90 for chunk in chunks)
    assert chunks[0].start_page == 1
    assert chunks[-1].end_page == 2
    assert chunk_pages(pages, target_size=60, maximum_size=90, overlap_size=10) == chunks


def test_legal_chunker_overlap_starts_at_complete_word_and_preserves_content() -> None:
    source = "uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce"
    chunks = chunk_pages(
        [CleanPage(1, source), CleanPage(2, "quince dieciseis diecisiete dieciocho")],
        target_size=35,
        maximum_size=50,
        overlap_size=13,
    )

    source_words = set(source.split()) | {"quince", "dieciseis", "diecisiete", "dieciocho"}
    assert all(chunk.char_count <= 50 for chunk in chunks)
    assert all(chunk.text.split()[0] in source_words for chunk in chunks)
    assert all(word in " ".join(chunk.text for chunk in chunks) for word in source_words)
    assert chunks[0].start_page == 1
    assert chunks[-1].end_page == 2


def test_extract_persists_pages_chunks_and_api_paginates(extraction_client) -> None:
    client, project_root, manager = extraction_client
    document = _register_document(project_root, manager, ["Artículo 1. Texto jurídico suficiente.", "Artículo 2. Más contenido."])

    extracted = client.post(f"/api/documents/{document.id}/extract")
    assert extracted.status_code == 200
    summary = extracted.json()
    assert summary["status"] == "extracted"
    assert summary["total_pages"] == 2
    assert summary["total_chunks"] >= 1
    pages = client.get(f"/api/documents/{document.id}/pages", params={"page": 1, "page_size": 1})
    assert pages.status_code == 200
    assert pages.json()["total"] == 2
    assert pages.json()["items"][0]["page_number"] == 1
    chunks = client.get(f"/api/documents/{document.id}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["items"][0]["chunk_index"] == 1
    assert client.post(f"/api/documents/{document.id}/extract").status_code == 409


def test_empty_pdf_fails_without_derived_rows(extraction_client) -> None:
    client, project_root, manager = extraction_client
    document = _register_document(project_root, manager, [""])

    response = client.post(f"/api/documents/{document.id}/extract")

    assert response.status_code == 422
    assert response.json()["detail"] == "PDF_NO_EXTRACTABLE_TEXT"
    assert client.get(f"/api/documents/{document.id}/pages").status_code == 409

    _create_pdf(
        project_root / "storage" / "documents" / "jurisprudencia" / "synthetic.pdf",
        ["Texto suficiente para el reintento."],
    )
    assert client.post(f"/api/documents/{document.id}/extract").status_code == 200
