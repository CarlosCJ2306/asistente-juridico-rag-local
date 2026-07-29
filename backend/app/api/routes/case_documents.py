"""API local de pertenencia documental explícita del expediente."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.cases import _call, _require_local
from app.cases.document_service import CaseDocumentService
from app.database.session import get_db_session
from app.schemas.case_document import (
    CaseDocumentAttach,
    CaseDocumentListResponse,
    CaseDocumentPublic,
    CaseDocumentRemove,
    CaseDocumentUpdate,
)
from app.services.conversation_principal import (
    ConversationPrincipal,
    get_conversation_principal,
)


router = APIRouter(prefix="/cases/{case_id}/documents", tags=["case-documents"])


@router.post("", response_model=CaseDocumentPublic, status_code=status.HTTP_201_CREATED)
async def attach_case_document(
    case_id: UUID,
    payload: CaseDocumentAttach,
    request: Request,
    principal: Annotated[
        ConversationPrincipal, Depends(get_conversation_principal)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaseDocumentPublic:
    _require_local(request)
    return await _call(
        CaseDocumentService(session).attach_document(case_id, payload, principal)
    )


@router.get("", response_model=CaseDocumentListResponse)
async def list_case_documents(
    case_id: UUID,
    request: Request,
    principal: Annotated[
        ConversationPrincipal, Depends(get_conversation_principal)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CaseDocumentListResponse:
    _require_local(request)
    return await _call(
        CaseDocumentService(session).list_documents(
            case_id, principal, page=page, page_size=page_size
        )
    )


@router.get("/{association_id}", response_model=CaseDocumentPublic)
async def get_case_document(
    case_id: UUID,
    association_id: UUID,
    request: Request,
    principal: Annotated[
        ConversationPrincipal, Depends(get_conversation_principal)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaseDocumentPublic:
    _require_local(request)
    return await _call(
        CaseDocumentService(session).get_document(
            case_id, association_id, principal
        )
    )


@router.patch("/{association_id}", response_model=CaseDocumentPublic)
async def update_case_document(
    case_id: UUID,
    association_id: UUID,
    payload: CaseDocumentUpdate,
    request: Request,
    principal: Annotated[
        ConversationPrincipal, Depends(get_conversation_principal)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaseDocumentPublic:
    _require_local(request)
    return await _call(
        CaseDocumentService(session).update_document(
            case_id, association_id, payload, principal
        )
    )


@router.delete("/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_case_document(
    case_id: UUID,
    association_id: UUID,
    payload: CaseDocumentRemove,
    request: Request,
    principal: Annotated[
        ConversationPrincipal, Depends(get_conversation_principal)
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    _require_local(request)
    await _call(
        CaseDocumentService(session).remove_document(
            case_id, association_id, payload, principal
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
