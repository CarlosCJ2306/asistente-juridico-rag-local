"""Operaciones asíncronas sobre metadatos de documentos, sin archivos físicos."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.Log import log_info, log_warning
from app.database.models.document import Document, DocumentStatus
from app.schemas.document import DocumentCreate, DocumentListFilters


class DocumentRepositoryError(RuntimeError):
    """Error base del repositorio documental."""


class DuplicateDocumentError(DocumentRepositoryError):
    """Un hash o ruta relativa ya está registrado."""

    def __init__(self, field: str, *, existing_document_id: UUID | None = None) -> None:
        super().__init__(f"Ya existe un documento con el mismo {field}")
        self.field = field
        self.existing_document_id = existing_document_id


class DocumentRepository:
    """Repositorios sin commit implícito; cada escritura realiza solo ``flush``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        data: DocumentCreate,
        *,
        use_savepoint: bool = True,
    ) -> Document:
        """Registra metadatos y hace flush; el consumidor controla el commit."""

        document = Document(**data.model_dump())
        try:
            if use_savepoint:
                async with self.session.begin_nested():
                    self.session.add(document)
                    await self.session.flush()
            else:
                self.session.add(document)
                await self.session.flush()
        except IntegrityError as exc:
            field = self._duplicate_field(exc)
            log_warning(
                "Conflicto al registrar metadatos documentales",
                operation="document_create",
                conflict_field=field,
            )
            raise DuplicateDocumentError(field) from exc

        await self.session.refresh(document)
        log_info(
            "Metadatos documentales registrados",
            operation="document_create",
            document_id=str(document.id),
            document_type=document.document_type.value,
            status=document.status.value,
            size_bytes=document.size_bytes,
        )
        return document

    async def get_by_id(
        self,
        document_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Document | None:
        """Obtiene un documento por UUID y excluye eliminados por defecto."""

        statement = select(Document).where(Document.id == document_id)
        if not include_deleted:
            statement = statement.where(Document.is_deleted.is_(False))
        return await self.session.scalar(statement)

    async def get_by_sha256(
        self,
        sha256: str,
        *,
        include_deleted: bool = False,
    ) -> Document | None:
        """Obtiene un documento por hash y excluye eliminados por defecto."""

        statement = select(Document).where(Document.sha256 == sha256.lower())
        if not include_deleted:
            statement = statement.where(Document.is_deleted.is_(False))
        return await self.session.scalar(statement)

    async def list(self, filters: DocumentListFilters) -> list[Document]:
        """Lista metadatos con paginación, filtros y exclusión lógica predeterminada."""

        statement = self._filtered_statement(filters).order_by(Document.created_at.desc())
        statement = statement.offset(filters.offset).limit(filters.limit)
        return list((await self.session.scalars(statement)).all())

    async def count(self, filters: DocumentListFilters) -> int:
        """Cuenta documentos con los mismos filtros aplicados al listado."""

        statement = select(func.count()).select_from(Document)
        statement = self._apply_filters(statement, filters)
        return int((await self.session.scalar(statement)) or 0)

    async def soft_delete(self, document_id: UUID) -> Document | None:
        """Marca el registro como eliminado; nunca borra una fila físicamente."""

        document = await self.get_by_id(document_id)
        if document is None:
            return None
        document.is_deleted = True
        document.deleted_at = datetime.now(timezone.utc)
        document.status = DocumentStatus.ARCHIVED
        await self.session.flush()
        await self.session.refresh(document)
        log_info(
            "Documento marcado como eliminado lógicamente",
            operation="document_soft_delete",
            document_id=str(document.id),
            status=document.status.value,
        )
        return document

    async def set_extraction_state(
        self,
        document: Document,
        status: DocumentStatus,
        *,
        error_code: str | None = None,
    ) -> None:
        """Actualiza solo el estado estable y el código seguro de extracción."""

        document.status = status
        document.error_code = error_code
        document.error_message = None
        await self.session.flush()

    @staticmethod
    def _duplicate_field(error: IntegrityError) -> str:
        """Clasifica una restricción SQLite sin registrar detalles internos."""

        detail = str(error.orig).lower() if error.orig is not None else ""
        if "sha256" in detail:
            return "sha256"
        if "relative_path" in detail:
            return "relative_path"
        return "campo único"

    @staticmethod
    def _filtered_statement(filters: DocumentListFilters):
        statement = select(Document)
        return DocumentRepository._apply_filters(statement, filters)

    @staticmethod
    def _apply_filters(statement, filters: DocumentListFilters):
        if not filters.include_deleted:
            statement = statement.where(Document.is_deleted.is_(False))
        if filters.document_type is not None:
            statement = statement.where(Document.document_type == filters.document_type)
        if filters.status is not None:
            statement = statement.where(Document.status == filters.status)
        return statement
