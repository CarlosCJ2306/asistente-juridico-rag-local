"""Caso de uso local para extraer, limpiar y persistir texto de PDFs."""

from __future__ import annotations

import time
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_error, log_exception, log_success
from app.core.config import settings
from app.core.paths import DOCUMENTS_DIR, PROJECT_ROOT
from app.database.models.document import DocumentStatus
from app.database.models.document_chunk import DocumentChunk
from app.database.models.document_page import DocumentPage
from app.database.repositories.document_chunk_repository import DocumentChunkRepository
from app.database.repositories.document_page_repository import DocumentPageRepository
from app.database.repositories.document_repository import DocumentRepository
from app.ingestion.legal_chunker import CleanPage, chunk_pages
from app.ingestion.pdf_reader import PdfReadError, read_pdf_pages, resolve_document_path
from app.ingestion.text_cleaner import clean_text
from app.schemas.document import ExtractionSummary


class DocumentExtractionError(RuntimeError):
    """Error de extracción con código estable y estado HTTP seguro."""

    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class DocumentExtractionService:
    """Coordina estados, PyMuPDF y una transacción de páginas/chunks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        documents_directory: Path = DOCUMENTS_DIR,
        project_root: Path = PROJECT_ROOT,
        minimum_extractable_chars: int = settings.pdf_min_extractable_chars,
        target_chunk_chars: int = settings.legal_chunk_target_chars,
        maximum_chunk_chars: int = settings.legal_chunk_max_chars,
        overlap_chunk_chars: int = settings.legal_chunk_overlap_chars,
    ) -> None:
        self.session = session
        self.documents_directory = documents_directory.resolve()
        self.project_root = project_root.resolve()
        self.minimum_extractable_chars = minimum_extractable_chars
        self.target_chunk_chars = target_chunk_chars
        self.maximum_chunk_chars = maximum_chunk_chars
        self.overlap_chunk_chars = overlap_chunk_chars
        self.documents = DocumentRepository(session)
        self.pages = DocumentPageRepository(session)
        self.chunks = DocumentChunkRepository(session)

    async def extract(self, document_id: UUID) -> ExtractionSummary:
        """Procesa un documento activo sin conservar resultados parciales."""

        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise DocumentExtractionError("DOCUMENT_NOT_FOUND", 404)
        if document.status in {DocumentStatus.EXTRACTED, DocumentStatus.EXTRACTING}:
            raise DocumentExtractionError("DOCUMENT_EXTRACTION_CONFLICT", 409)
        if document.status not in {DocumentStatus.PENDING_EXTRACTION, DocumentStatus.EXTRACTION_FAILED}:
            raise DocumentExtractionError("DOCUMENT_STATUS_INVALID", 409)

        await self.documents.set_extraction_state(document, DocumentStatus.EXTRACTING)
        await self.session.commit()
        started_at = time.perf_counter()
        try:
            path = resolve_document_path(
                document.relative_path,
                documents_directory=self.documents_directory,
                project_root=self.project_root,
            )
            raw_pages = read_pdf_pages(path)
            clean_pages = [CleanPage(page.page_number, clean_text(page.raw_text)) for page in raw_pages]
            total_characters = sum(len(page.text) for page in clean_pages)
            if total_characters < self.minimum_extractable_chars:
                raise DocumentExtractionError("PDF_NO_EXTRACTABLE_TEXT", 422)
            chunks = chunk_pages(
                clean_pages,
                target_size=self.target_chunk_chars,
                maximum_size=self.maximum_chunk_chars,
                overlap_size=self.overlap_chunk_chars,
            )
            await self.pages.delete_by_document(document.id)
            await self.chunks.delete_by_document(document.id)
            await self.pages.bulk_create(
                [
                    DocumentPage(
                        document_id=document.id,
                        page_number=page.page_number,
                        text=page.text,
                        char_count=len(page.text),
                    )
                    for page in clean_pages
                ]
            )
            await self.chunks.bulk_create(
                [
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        char_count=chunk.char_count,
                        word_count=chunk.word_count,
                        start_page=chunk.start_page,
                        end_page=chunk.end_page,
                    )
                    for chunk in chunks
                ]
            )
            await self.documents.set_extraction_state(document, DocumentStatus.EXTRACTED)
            await self.session.commit()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_success(
                "Extracción documental completada",
                operation="document_extraction",
                document_id=str(document.id),
                total_pages=len(clean_pages),
                total_chunks=len(chunks),
                duration_ms=duration_ms,
            )
            return ExtractionSummary(
                document_id=document.id,
                status=DocumentStatus.EXTRACTED,
                total_pages=len(clean_pages),
                total_chunks=len(chunks),
                total_characters=total_characters,
            )
        except PdfReadError as exc:
            raise await self._fail(document.id, exc.code, 422) from exc
        except DocumentExtractionError as exc:
            raise await self._fail(document.id, exc.code, exc.status_code) from exc
        except Exception as exc:
            log_exception(
                "Falló la extracción documental",
                operation="document_extraction",
                document_id=str(document.id),
                exception_type=type(exc).__name__,
            )
            raise await self._fail(document.id, "PDF_EXTRACTION_ERROR", 500) from exc

    async def _fail(self, document_id: UUID, code: str, status_code: int) -> DocumentExtractionError:
        await self.session.rollback()
        document = await self.documents.get_by_id(document_id)
        if document is not None:
            await self.pages.delete_by_document(document_id)
            await self.chunks.delete_by_document(document_id)
            await self.documents.set_extraction_state(
                document,
                DocumentStatus.EXTRACTION_FAILED,
                error_code=code,
            )
            await self.session.commit()
        log_error(
            "Extracción documental no completada",
            operation="document_extraction",
            document_id=str(document_id),
            error_code=code,
        )
        return DocumentExtractionError(code, status_code)

    async def ensure_extracted_document(self, document_id: UUID):
        """Comprueba existencia y disponibilidad de resultados extraídos."""

        document = await self.documents.get_by_id(document_id)
        if document is None:
            raise DocumentExtractionError("DOCUMENT_NOT_FOUND", 404)
        if document.status is not DocumentStatus.EXTRACTED:
            raise DocumentExtractionError("DOCUMENT_NOT_EXTRACTED", 409)
        return document
