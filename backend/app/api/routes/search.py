"""Endpoint local de búsqueda textual FTS5 sin registrar consultas."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.database.session import get_db_session
from app.schemas.semantic_search import (
    SemanticRebuildResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticStatusResponse,
)
from app.schemas.text_search import TextSearchPage, TextSearchRequest
from app.services.semantic_index_service import SemanticIndexService, SemanticServiceError
from app.services.semantic_search_service import SemanticSearchService
from app.services.text_search_service import TextSearchService, TextSearchValidationError


router = APIRouter(prefix="/search", tags=["search"])


def _semantic_http_error(error: SemanticServiceError) -> HTTPException:
    if error.code == "SEMANTIC_INDEX_BUSY":
        status_code = 409
    elif error.code in {
        "CHROMA_DEPENDENCY_MISSING",
        "VECTOR_STORE_PATH_INVALID",
        "EMBEDDING_MODEL_NOT_LOADED",
        "SEMANTIC_INDEX_NOT_READY",
        "SEMANTIC_INDEX_STATE_INVALID",
        "SEMANTIC_INDEX_INCOMPATIBLE",
    }:
        status_code = 503
    elif error.code in {
        "SEMANTIC_QUERY_EMPTY",
        "SEMANTIC_QUERY_INVALID",
        "SEMANTIC_QUERY_TOO_LONG",
    }:
        status_code = 422
    else:
        status_code = 500
    return HTTPException(status_code=status_code, detail=error.code)


@router.post("/text", response_model=TextSearchPage)
async def search_text(
    payload: TextSearchRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TextSearchPage:
    """Busca chunks activos con ranking BM25 y trazabilidad documental."""

    service = TextSearchService(session)
    try:
        return await service.search(payload, request_id=getattr(request.state, "request_id", None))
    except TextSearchValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TextSearchRepositoryError as exc:
        status_code = 503 if exc.code in {"FTS5_NOT_AVAILABLE", "TEXT_SEARCH_INDEX_NOT_READY"} else 500
        raise HTTPException(status_code=status_code, detail=exc.code) from exc


@router.get("/semantic/status", response_model=SemanticStatusResponse)
async def semantic_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticStatusResponse:
    """Consulta estado operativo sin cargar modelos ni crear el índice."""

    return await SemanticIndexService(session).status()


@router.post("/semantic/rebuild", response_model=SemanticRebuildResponse)
async def rebuild_semantic_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticRebuildResponse:
    """Reconstruye explícitamente el índice mediante una colección temporal."""

    try:
        return await SemanticIndexService(session).rebuild(
            request_id=getattr(request.state, "request_id", None)
        )
    except SemanticServiceError as exc:
        raise _semantic_http_error(exc) from exc


@router.post("/semantic", response_model=SemanticSearchResponse)
async def search_semantic(
    payload: SemanticSearchRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticSearchResponse:
    """Busca por distancia coseno y valida cada resultado contra SQLite."""

    index_service = SemanticIndexService(session)
    try:
        return await SemanticSearchService(index_service).search(
            payload,
            request_id=getattr(request.state, "request_id", None),
        )
    except SemanticServiceError as exc:
        raise _semantic_http_error(exc) from exc
