"""Endpoint local de búsqueda textual FTS5 sin registrar consultas."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.database.session import get_db_session
from app.schemas.text_search import TextSearchPage, TextSearchRequest
from app.services.text_search_service import TextSearchService, TextSearchValidationError


router = APIRouter(prefix="/search", tags=["search"])


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
