"""Endpoints de metadatos y carga controlada de documentos PDF."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.document import DocumentStatus, DocumentType
from app.database.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.database.session import get_db_session
from app.schemas.document import DocumentListFilters, DocumentPage, DocumentRead
from app.services.document_service import (
    DocumentService,
    DocumentStorageError,
    DocumentTooLargeError,
    InvalidDocumentError,
)


router = APIRouter(prefix="/documents", tags=["documents"])


def _service(session: AsyncSession) -> DocumentService:
    return DocumentService(session)


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    document_type: Annotated[DocumentType, Form(...)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentRead | ORJSONResponse:
    """Carga un PDF en temporal, lo valida y lo registra de forma atómica."""

    try:
        return await _service(session).upload_pdf(file, document_type)
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
    documents = await repository.list(filters)
    total = await repository.count(filters)
    return DocumentPage(
        items=[DocumentRead.model_validate(document) for document in documents],
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
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Elimina únicamente el registro lógico; el PDF se conserva en disco."""

    if not await _service(session).soft_delete(document_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return Response(status_code=204)
