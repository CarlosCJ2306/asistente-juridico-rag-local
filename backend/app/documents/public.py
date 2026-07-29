"""Acceso público seguro a documentos y extracción, sin exponer ORM."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentRead, ExtractionSummary
from app.services.document_extraction_service import DocumentExtractionService
from app.services.document_governance_service import DocumentGovernanceService


@dataclass(frozen=True, slots=True)
class DocumentBatch:
    """Resultado ordenado de una resolución documental por lote."""

    items: tuple[DocumentRead, ...]
    missing_document_ids: tuple[UUID, ...]


class DocumentCatalogFacade:
    """Fachada de lectura que nunca devuelve rutas, hashes ni modelos ORM."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = DocumentRepository(session)
        self._governance = DocumentGovernanceService()

    async def resolve_many(
        self,
        document_ids: tuple[UUID, ...],
        *,
        include_deleted: bool = False,
    ) -> DocumentBatch:
        ordered_ids = tuple(dict.fromkeys(document_ids))
        resolved = await self._repository.get_by_ids(
            list(ordered_ids), include_deleted=include_deleted
        )
        return DocumentBatch(
            items=tuple(
                self._governance.to_public_read(resolved[document_id])
                for document_id in ordered_ids
                if document_id in resolved
            ),
            missing_document_ids=tuple(
                document_id for document_id in ordered_ids if document_id not in resolved
            ),
        )


class DocumentExtractionFacade:
    """Punto único para consultar o solicitar la extracción oficial."""

    def __init__(self, session: AsyncSession) -> None:
        self._catalog = DocumentCatalogFacade(session)
        self._service = DocumentExtractionService(session)

    async def status(self, document_id: UUID) -> DocumentRead | None:
        batch = await self._catalog.resolve_many((document_id,))
        return batch.items[0] if batch.items else None

    async def request(self, document_id: UUID) -> ExtractionSummary:
        return await self._service.extract(document_id)
