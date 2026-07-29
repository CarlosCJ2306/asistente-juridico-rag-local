"""API local mínima del núcleo persistente Case."""

from __future__ import annotations

import ipaddress
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases.domain import CaseStatus
from app.cases.errors import CaseError
from app.cases.service import CaseService
from app.database.session import get_db_session
from app.schemas.case import CaseActionRequest, CaseCreate, CaseListResponse, CasePublic, CaseUpdate
from app.services.conversation_principal import ConversationPrincipal, get_conversation_principal


router = APIRouter(prefix="/cases", tags=["cases"])


def _require_local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host != "testclient":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="CASE_LOCAL_ONLY_REQUIRED") from exc


def _http_error(error: CaseError) -> HTTPException:
    if error.code in {
        "CASE_NOT_FOUND",
        "CASE_EXPIRED",
        "CASE_DOCUMENT_NOT_FOUND",
    }:
        code = status.HTTP_404_NOT_FOUND
    elif error.code in {
        "CASE_VERSION_CONFLICT",
        "CASE_INVALID_TRANSITION",
        "CASE_ARCHIVED_READ_ONLY",
        "CASE_DOCUMENT_DUPLICATE",
        "CASE_DOCUMENT_VERSION_CONFLICT",
    }:
        code = status.HTTP_409_CONFLICT
    elif error.code in {
        "CASE_RETENTION_INVALID",
        "CASE_TITLE_INVALID",
        "CASE_DOCUMENT_LAYER_NOT_ALLOWED",
        "CASE_DOCUMENT_UNAVAILABLE",
        "CASE_DOCUMENT_EXPIRED",
        "CASE_DOCUMENT_INVALID_PURPOSE",
        "CASE_DOCUMENT_INVALID_ORDER",
    }:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return HTTPException(status_code=code, detail=error.code)


async def _call(operation):
    try:
        return await operation
    except CaseError as exc:
        raise _http_error(exc) from exc


@router.post("", response_model=CasePublic, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CasePublic:
    _require_local(request)
    return await _call(CaseService(session).create_case(payload, principal))


@router.get("", response_model=CaseListResponse)
async def list_cases(
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CaseListResponse:
    _require_local(request)
    return await CaseService(session).list_cases(
        principal, page=page, page_size=page_size
    )


@router.get("/{case_id}", response_model=CasePublic)
async def get_case(
    case_id: UUID,
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CasePublic:
    _require_local(request)
    return await _call(CaseService(session).get_case(case_id, principal))


@router.patch("/{case_id}", response_model=CasePublic)
async def update_case(
    case_id: UUID,
    payload: CaseUpdate,
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CasePublic:
    _require_local(request)
    return await _call(CaseService(session).update_case(case_id, payload, principal))


async def _transition(
    case_id: UUID,
    payload: CaseActionRequest,
    principal: ConversationPrincipal,
    session: AsyncSession,
    target: CaseStatus,
) -> CasePublic:
    return await _call(
        CaseService(session).transition_case(case_id, payload, principal, target=target)
    )


@router.post("/{case_id}/activate", response_model=CasePublic)
async def activate_case(case_id: UUID, payload: CaseActionRequest, request: Request, principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)], session: Annotated[AsyncSession, Depends(get_db_session)]) -> CasePublic:
    _require_local(request)
    return await _transition(case_id, payload, principal, session, CaseStatus.ACTIVE)


@router.post("/{case_id}/review", response_model=CasePublic)
async def review_case(case_id: UUID, payload: CaseActionRequest, request: Request, principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)], session: Annotated[AsyncSession, Depends(get_db_session)]) -> CasePublic:
    _require_local(request)
    return await _transition(case_id, payload, principal, session, CaseStatus.IN_REVIEW)


@router.post("/{case_id}/close", response_model=CasePublic)
async def close_case(case_id: UUID, payload: CaseActionRequest, request: Request, principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)], session: Annotated[AsyncSession, Depends(get_db_session)]) -> CasePublic:
    _require_local(request)
    return await _transition(case_id, payload, principal, session, CaseStatus.CLOSED)


@router.post("/{case_id}/archive", response_model=CasePublic)
async def archive_case(case_id: UUID, payload: CaseActionRequest, request: Request, principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)], session: Annotated[AsyncSession, Depends(get_db_session)]) -> CasePublic:
    _require_local(request)
    return await _transition(case_id, payload, principal, session, CaseStatus.ARCHIVED)


@router.post("/{case_id}/restore", response_model=CasePublic)
async def restore_case(case_id: UUID, payload: CaseActionRequest, request: Request, principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)], session: Annotated[AsyncSession, Depends(get_db_session)]) -> CasePublic:
    _require_local(request)
    return await _call(CaseService(session).restore_case(case_id, payload, principal))


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    request: Request,
    principal: Annotated[ConversationPrincipal, Depends(get_conversation_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    _require_local(request)
    await _call(CaseService(session).delete_case(case_id, expected_version, principal))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
