"""Endpoints de metadatos y carga controlada de documentos PDF."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.database.models.document import (
    DocumentStatus,
    DocumentType,
    KnowledgeLayer,
    SourceKind,
)
from app.database.repositories.document_chunk_repository import DocumentChunkRepository
from app.database.repositories.document_page_repository import DocumentPageRepository
from app.database.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.database.repositories.document_processing_job_repository import (
    DocumentProcessingJobRepository,
)
from app.database.session import get_db_session
from app.core.Log import log_error
from app.schemas.document import (
    DocumentListFilters,
    DocumentPage,
    DocumentRead,
    DocumentUploadGovernance,
    ExtractedChunkRead,
    ExtractedChunksPage,
    ExtractedPageRead,
    ExtractedPagesPage,
    ExtractionSummary,
)
from app.services.document_extraction_service import (
    DocumentExtractionError,
    DocumentExtractionService,
)
from app.services.document_governance_service import (
    DocumentGovernanceError,
    DocumentGovernanceService,
)
from app.services.document_service import (
    DocumentService,
    DocumentStorageError,
    DocumentTooLargeError,
    InvalidDocumentError,
)


router = APIRouter(prefix="/documents", tags=["documents"])


def _service(session: AsyncSession) -> DocumentService:
    return DocumentService(session)


def _extraction_service(session: AsyncSession) -> DocumentExtractionService:
    return DocumentExtractionService(session)


def _governance_service(session: AsyncSession) -> DocumentGovernanceService:
    return DocumentGovernanceService(session)


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    document_type: Annotated[DocumentType, Form(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    display_name: Annotated[str | None, Form()] = None,
    knowledge_layer: Annotated[KnowledgeLayer, Form()] = KnowledgeLayer.PRIVATE_LIBRARY,
    source_kind: Annotated[SourceKind, Form()] = SourceKind.LOCAL_UPLOAD,
    expires_at: Annotated[datetime | None, Form()] = None,
) -> DocumentRead | ORJSONResponse:
    """Carga un PDF en temporal, lo valida y lo registra de forma atómica."""

    try:
        governance = DocumentUploadGovernance(
            display_name=display_name,
            knowledge_layer=knowledge_layer,
            source_kind=source_kind,
            expires_at=expires_at,
        )
        created = await _service(session).upload_pdf(file, document_type, governance)
        try:
            await DocumentProcessingJobRepository(session).create_upload_job(
                document_id=created.id,
                knowledge_layer=created.knowledge_layer,
                public_name=created.display_name,
            )
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            log_error(
                "No fue posible encolar el documento cargado",
                operation="document_processing_enqueue",
                error_code="DOCUMENT_PROCESSING_QUEUE_NOT_READY",
            )
        return created
    except (ValidationError, DocumentGovernanceError) as exc:
        raise HTTPException(
            status_code=422,
            detail="DOCUMENT_GOVERNANCE_INVALID",
        ) from exc
    except DuplicateDocumentError as exc:
        content = {"detail": "El documento ya está registrado"}
        if exc.existing_document_id is not None:
            content["existing_document_id"] = str(exc.existing_document_id)
        return ORJSONResponse(status_code=409, content=content)
    except InvalidDocumentError as exc:
        raise _bad_request(exc) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=500,
            detail="No fue posible almacenar el documento",
        ) from exc


@router.get("", response_model=DocumentPage)
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    document_type: DocumentType | None = None,
    status: DocumentStatus | None = None,
) -> DocumentPage:
    """Lista documentos no eliminados con paginación y filtros simples."""

    filters = DocumentListFilters(
        offset=(page - 1) * page_size,
        limit=page_size,
        document_type=document_type,
        status=status,
    )
    repository = DocumentRepository(session)
    governance = _governance_service(session)
    documents = await repository.list(filters)
    total = await repository.count(filters)
    return DocumentPage(
        items=[governance.to_public_read(document) for document in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentRead:
    """Obtiene metadatos de un documento activo sin exponer rutas absolutas."""

    document = await DocumentRepository(session).get_by_id(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return _governance_service(session).to_public_read(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Elimina únicamente el registro lógico; el PDF se conserva en disco."""

    if not await _service(session).soft_delete(document_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return Response(status_code=204)


@router.post("/{document_id}/extract", response_model=ExtractionSummary)
async def extract_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExtractionSummary:
    """Ejecuta manualmente la extracción local de un PDF previamente cargado."""

    try:
        return await _extraction_service(session).extract(document_id)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.get("/{document_id}/pages", response_model=ExtractedPagesPage)
async def list_document_pages(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ExtractedPagesPage:
    """Lista páginas extraídas en orden, con paginación."""

    service = _extraction_service(session)
    try:
        await service.ensure_extracted_document(document_id)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    repository = DocumentPageRepository(session)
    offset = (page - 1) * page_size
    pages = await repository.list_by_document(document_id, offset=offset, limit=page_size)
    return ExtractedPagesPage(
        items=[ExtractedPageRead.model_validate(item) for item in pages],
        total=await repository.count_by_document(document_id),
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}/chunks", response_model=ExtractedChunksPage)
async def list_document_chunks(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ExtractedChunksPage:
    """Lista chunks jurídicos extraídos en orden, con paginación."""

    service = _extraction_service(session)
    try:
        await service.ensure_extracted_document(document_id)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    repository = DocumentChunkRepository(session)
    offset = (page - 1) * page_size
    chunks = await repository.list_by_document(document_id, offset=offset, limit=page_size)
    return ExtractedChunksPage(
        items=[ExtractedChunkRead.model_validate(item) for item in chunks],
        total=await repository.count_by_document(document_id),
        page=page,
        page_size=page_size,
    )
