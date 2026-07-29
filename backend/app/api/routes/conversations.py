"""API de conversaciones RAG persistentes para sesiones invitadas aisladas."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.chat import _rag_http_error
from app.database.models.conversation import ConversationStatus
from app.database.repositories.text_search_repository import TextSearchRepositoryError
from app.database.session import get_db_session
from app.schemas.conversation import (
    IDEMPOTENCY_KEY_PATTERN,
    ConversationCreate,
    ConversationDetail,
    ConversationMessageCreate,
    ConversationPage,
    ConversationRead,
    ConversationTurnResponse,
    ConversationUpdate,
)
from app.services.conversation_principal import (
    ConversationPrincipal,
    get_conversation_principal,
)
from app.services.conversation_service import ConversationError, ConversationService
from app.services.hybrid_search_service import HybridSearchError
from app.services.rag_chat_service import RagChatError
from app.services.semantic_index_service import SemanticServiceError


router = APIRouter(prefix="/conversations", tags=["conversations"])


def _conversation_http_error(error: ConversationError) -> HTTPException:
    if error.code == "CONVERSATION_NOT_FOUND":
        code = status.HTTP_404_NOT_FOUND
    elif error.code in {"CONVERSATION_ARCHIVED", "CONVERSATION_MESSAGE_BUSY"}:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return HTTPException(status_code=code, detail=error.code)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRead:
    return await ConversationService(session).create(payload, principal)


@router.get("", response_model=ConversationPage)
async def list_conversations(
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    conversation_status: Annotated[ConversationStatus, Query(alias="status")] = (
        ConversationStatus.ACTIVE
    ),
) -> ConversationPage:
    return await ConversationService(session).list_page(
        principal, page=page, page_size=page_size, status=conversation_status
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationDetail:
    try:
        return await ConversationService(session).detail(conversation_id, principal)
    except ConversationError as exc:
        raise _conversation_http_error(exc) from exc


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRead:
    try:
        return await ConversationService(session).update(conversation_id, payload, principal)
    except ConversationError as exc:
        raise _conversation_http_error(exc) from exc


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    try:
        await ConversationService(session).delete(conversation_id, principal)
    except ConversationError as exc:
        raise _conversation_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_conversation_message(
    conversation_id: UUID,
    payload: ConversationMessageCreate,
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ConversationTurnResponse:
    if idempotency_key is not None and not IDEMPOTENCY_KEY_PATTERN.fullmatch(
        idempotency_key
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CONVERSATION_IDEMPOTENCY_KEY_INVALID",
        )
    try:
        return await ConversationService(session).add_message(
            conversation_id,
            payload,
            principal,
            idempotency_key=idempotency_key,
            request_id=getattr(request.state, "request_id", None),
        )
    except ConversationError as exc:
        raise _conversation_http_error(exc) from exc
    except (
        RagChatError,
        HybridSearchError,
        TextSearchRepositoryError,
        SemanticServiceError,
    ) as exc:
        raise _rag_http_error(exc) from exc
