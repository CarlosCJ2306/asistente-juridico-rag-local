"""Flujo seguro de carga PDF que coordina almacenamiento y metadatos SQLite."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_error, log_success, log_warning
from app.core.config import settings
from app.core.paths import DOCUMENTS_DIR, PROJECT_ROOT, UPLOADS_TEMP_DIR
from app.database.models.document import DocumentStatus, DocumentType
from app.database.repositories.document_repository import (
    DocumentRepository,
    DuplicateDocumentError,
)
from app.schemas.document import DocumentCreate, DocumentRead


PDF_SIGNATURE = b"%PDF-"
DOCUMENT_CATEGORY_DIRECTORIES = {
    DocumentType.EXPEDIENTE: "expedientes",
    DocumentType.NORMATIVA: "normativa",
    DocumentType.JURISPRUDENCIA: "jurisprudencia",
    DocumentType.OTRO: "otros",
}


class DocumentServiceError(RuntimeError):
    """Error base de carga documental que no expone detalles internos."""


class InvalidDocumentError(DocumentServiceError):
    """Los metadatos o firma del archivo no corresponden a un PDF aceptado."""


class DocumentTooLargeError(DocumentServiceError):
    """El contenido excede el límite configurado durante la carga."""


class DocumentStorageError(DocumentServiceError):
    """Falló la coordinación entre almacenamiento temporal y base de datos."""


class DocumentService:
    """Orquesta archivos y transacciones sin introducir lógica de archivos al repositorio."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        temporary_directory: Path = UPLOADS_TEMP_DIR,
        documents_directory: Path = DOCUMENTS_DIR,
        project_root: Path = PROJECT_ROOT,
        maximum_size_bytes: int = settings.document_max_size_bytes,
        chunk_size_bytes: int = settings.document_upload_chunk_size_bytes,
    ) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.temporary_directory = temporary_directory.resolve()
        self.documents_directory = documents_directory.resolve()
        self.project_root = project_root.resolve()
        self.maximum_size_bytes = maximum_size_bytes
        self.chunk_size_bytes = chunk_size_bytes
        if maximum_size_bytes <= 0 or chunk_size_bytes <= 0:
            raise ValueError("Los límites de carga deben ser mayores que cero")
        if chunk_size_bytes > maximum_size_bytes:
            raise ValueError("El tamaño de bloque no puede exceder el máximo permitido")

    async def upload_pdf(
        self,
        upload: UploadFile,
        document_type: DocumentType,
    ) -> DocumentRead:
        """Valida, almacena y registra un PDF; confirma solo tras moverlo con éxito."""

        temporary_path: Path | None = None
        final_path: Path | None = None
        moved_to_final_path = False
        storage_confirmed = False
        started_at = time.perf_counter()
        try:
            original_filename = self._normalize_original_filename(upload.filename)
            self._validate_declared_metadata(original_filename, upload.content_type)
            temporary_path, size_bytes, sha256 = await self._write_temporary_file(upload)
            self._validate_pdf_signature(temporary_path)

            existing = await self.repository.get_by_sha256(
                sha256,
                include_deleted=True,
            )
            if existing is not None:
                raise DuplicateDocumentError(
                    "sha256",
                    existing_document_id=existing.id,
                )

            stored_filename = f"{uuid4()}.pdf"
            final_path = self._build_final_path(document_type, stored_filename)
            document = await self.repository.create(
                DocumentCreate(
                    original_filename=original_filename,
                    stored_filename=stored_filename,
                    relative_path=self._to_project_relative_path(final_path),
                    document_type=document_type,
                    mime_type="application/pdf",
                    extension=".pdf",
                    size_bytes=size_bytes,
                    sha256=sha256,
                    status=DocumentStatus.PENDING_EXTRACTION,
                )
            )

            self._move_to_final_path(temporary_path, final_path)
            moved_to_final_path = True
            temporary_path = None
            try:
                await self.session.commit()
                await self.session.refresh(document)
                storage_confirmed = True
            except Exception as exc:
                await self.session.rollback()
                raise DocumentStorageError(
                    "No fue posible confirmar el registro documental"
                ) from exc

            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_success(
                "Documento PDF almacenado y registrado",
                operation="document_upload",
                document_id=str(document.id),
                document_type=document.document_type.value,
                status=document.status.value,
                size_bytes=document.size_bytes,
                sha256_prefix=sha256[:12],
                duration_ms=duration_ms,
            )
            return DocumentRead.model_validate(document)
        except DuplicateDocumentError:
            await self.session.rollback()
            raise
        except (InvalidDocumentError, DocumentTooLargeError):
            await self.session.rollback()
            raise
        except DocumentStorageError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            log_error(
                "Falló la carga documental",
                operation="document_upload",
                exception_type=type(exc).__name__,
            )
            raise DocumentStorageError("No fue posible almacenar el documento") from exc
        finally:
            if temporary_path is not None:
                self._remove_file(temporary_path)
            if moved_to_final_path and not storage_confirmed and final_path is not None:
                self._remove_file(final_path)
            await upload.close()

    async def soft_delete(self, document_id: UUID) -> bool:
        """Elimina lógicamente un registro y confirma sin tocar el PDF original."""

        document = await self.repository.soft_delete(document_id)
        if document is None:
            return False
        await self.session.commit()
        return True

    def _normalize_original_filename(self, filename: str | None) -> str:
        if filename is None or not filename.strip():
            raise InvalidDocumentError("El nombre del archivo es obligatorio")
        if any(ord(character) < 32 for character in filename):
            raise InvalidDocumentError("El nombre del archivo contiene caracteres no permitidos")
        normalized = PurePosixPath(filename.replace("\\", "/")).name.strip()
        if not normalized or normalized in {".", ".."}:
            raise InvalidDocumentError("El nombre del archivo no es válido")
        if len(normalized) > 255:
            raise InvalidDocumentError("El nombre del archivo excede el límite permitido")
        return normalized

    @staticmethod
    def _validate_declared_metadata(filename: str, content_type: str | None) -> None:
        if not filename.lower().endswith(".pdf"):
            raise InvalidDocumentError("Solo se aceptan archivos con extensión .pdf")
        if content_type != "application/pdf":
            raise InvalidDocumentError("El tipo MIME debe ser application/pdf")

    async def _write_temporary_file(self, upload: UploadFile) -> tuple[Path, int, str]:
        self.temporary_directory.mkdir(parents=True, exist_ok=True)
        temporary_path = self._safe_child_path(
            self.temporary_directory,
            f"{uuid4()}.part",
        )
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with temporary_path.open("xb") as temporary_file:
                while chunk := await upload.read(self.chunk_size_bytes):
                    size_bytes += len(chunk)
                    if size_bytes > self.maximum_size_bytes:
                        raise DocumentTooLargeError(
                            "El archivo excede el tamaño máximo permitido"
                        )
                    digest.update(chunk)
                    temporary_file.write(chunk)
        except Exception:
            self._remove_file(temporary_path)
            raise
        if size_bytes == 0:
            self._remove_file(temporary_path)
            raise InvalidDocumentError("El archivo PDF no puede estar vacío")
        return temporary_path, size_bytes, digest.hexdigest()

    @staticmethod
    def _validate_pdf_signature(temporary_path: Path) -> None:
        with temporary_path.open("rb") as temporary_file:
            if temporary_file.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
                raise InvalidDocumentError("El contenido no contiene una firma PDF válida")

    def _build_final_path(self, document_type: DocumentType, filename: str) -> Path:
        category = DOCUMENT_CATEGORY_DIRECTORIES[document_type]
        category_directory = self._safe_child_path(self.documents_directory, category)
        category_directory.mkdir(parents=True, exist_ok=True)
        return self._safe_child_path(category_directory, filename)

    def _to_project_relative_path(self, path: Path) -> str:
        try:
            relative_path = path.resolve().relative_to(self.project_root).as_posix()
        except ValueError as exc:
            raise DocumentStorageError("La ruta documental está fuera del almacenamiento permitido") from exc
        if not relative_path.startswith("storage/documents/"):
            raise DocumentStorageError("La ruta documental no pertenece al almacenamiento permitido")
        return relative_path

    @staticmethod
    def _safe_child_path(directory: Path, child_name: str) -> Path:
        root = directory.resolve()
        candidate = (root / child_name).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise DocumentStorageError("La ruta de almacenamiento no es segura") from exc
        return candidate

    @staticmethod
    def _move_to_final_path(temporary_path: Path, final_path: Path) -> None:
        if final_path.exists():
            raise DocumentStorageError("La ruta definitiva ya existe")
        try:
            os.replace(temporary_path, final_path)
        except OSError as exc:
            raise DocumentStorageError("No fue posible mover el archivo temporal") from exc

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError as exc:
            log_warning(
                "No fue posible limpiar un archivo temporal o definitivo",
                operation="document_storage_cleanup",
                exception_type=type(exc).__name__,
            )
