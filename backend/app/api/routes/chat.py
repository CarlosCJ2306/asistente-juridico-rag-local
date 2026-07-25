"""API stateless de Chat RAG local."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.database.session import get_db_session
from app.schemas.rag_chat import RagChatRequest, RagChatResponse
from app.services.hybrid_search_service import HybridSearchError
from app.services.rag_chat_service import RagChatError, RagChatService
from app.services.semantic_index_service import SemanticServiceError


router = APIRouter(prefix="/chat", tags=["chat"])


def _rag_http_error(error: Exception) -> HTTPException:
    code = getattr(error, "code", "RAG_GENERATION_ERROR")
    if code == "RAG_GENERATION_BUSY":
        status_code = 409
    elif code in {
        "RAG_LLM_NOT_LOADED",
        "RAG_RETRIEVAL_UNAVAILABLE",
        "RAG_CONTEXT_UNAVAILABLE",
        "FTS5_NOT_AVAILABLE",
        "TEXT_SEARCH_INDEX_NOT_READY",
        "CHROMA_DEPENDENCY_MISSING",
        "SEMANTIC_INDEX_NOT_READY",
        "SEMANTIC_INDEX_STATE_INVALID",
        "SEMANTIC_INDEX_INCOMPATIBLE",
        "EMBEDDING_MODEL_NOT_LOADED",
        "HYBRID_SEARCH_UNAVAILABLE",
    }:
        status_code = 503
    else:
        status_code = 500
    return HTTPException(status_code=status_code, detail=code)


@router.post("/rag", response_model=RagChatResponse)
async def chat_rag(
    payload: RagChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RagChatResponse:
    """Recupera contexto y genera una respuesta local sin historial."""

    service = RagChatService(session)
    try:
        return await service.chat(
            payload, request_id=getattr(request.state, "request_id", None)
        )
    except (
        RagChatError,
        HybridSearchError,
        TextSearchRepositoryError,
        SemanticServiceError,
    ) as exc:
        raise _rag_http_error(exc) from exc
