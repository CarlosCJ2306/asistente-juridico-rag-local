"""API local y tipada para la Matriz HPN manual."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import HpnError
from app.database.session import get_db_session
from app.schemas.hpn import (
    HpnMatrixCreate,
    HpnMatrixDetail,
    HpnMatrixList,
    HpnMatrixRead,
    HpnMatrixUpdate,
    HpnNodeCreate,
    HpnNodeRead,
    HpnNodeUpdate,
    HpnRelationCreate,
    HpnRelationRead,
    HpnRelationUpdate,
    HpnSourceCreate,
    HpnSourceRead,
    HpnValidationSummary,
)
from app.services.hpn_service import HpnService


router = APIRouter(prefix="/hpn", tags=["hpn"])


def hpn_http_error(error: HpnError) -> HTTPException:
    if error.code.endswith("_NOT_FOUND"):
        status = 404
    elif error.code in {
        "HPN_DUPLICATE_SOURCE",
        "HPN_DUPLICATE_RELATION",
        "HPN_REVIEW_INCOMPLETE",
        "HPN_CONFLICT",
        "HPN_MATRIX_DELETED",
        "HPN_MATRIX_ARCHIVED",
    }:
        status = 409
    elif error.code in {
        "HPN_SOURCE_INVALID",
        "HPN_SOURCE_STALE",
        "HPN_RELATION_ENDPOINT_INVALID",
        "HPN_LIMIT_EXCEEDED",
        "HPN_VALIDATION_ERROR",
    }:
        status = 422
    else:
        status = 500
    return HTTPException(status_code=status, detail=error.code)


async def _call(operation):
    try:
        return await operation
    except HpnError as exc:
        raise hpn_http_error(exc) from exc


@router.post("/matrices", response_model=HpnMatrixRead, status_code=201)
async def create_matrix(
    payload: HpnMatrixCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnMatrixRead:
    return await _call(HpnService(session).create_matrix(payload))


@router.get("/matrices", response_model=HpnMatrixList)
async def list_matrices(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> HpnMatrixList:
    return await _call(
        HpnService(session).list_matrices(page=page, page_size=page_size)
    )


@router.get("/matrices/{matrix_id}", response_model=HpnMatrixDetail)
async def get_matrix(
    matrix_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnMatrixDetail:
    return await _call(HpnService(session).detail(matrix_id))


@router.patch("/matrices/{matrix_id}", response_model=HpnMatrixRead)
async def update_matrix(
    matrix_id: UUID,
    payload: HpnMatrixUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnMatrixRead:
    return await _call(HpnService(session).update_matrix(matrix_id, payload))


@router.delete("/matrices/{matrix_id}", status_code=204)
async def delete_matrix(
    matrix_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _call(HpnService(session).delete_matrix(matrix_id))
    return Response(status_code=204)


@router.get("/matrices/{matrix_id}/validation", response_model=HpnValidationSummary)
async def validate_matrix(
    matrix_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnValidationSummary:
    return await _call(HpnService(session).validation(matrix_id))


@router.post("/matrices/{matrix_id}/nodes", response_model=HpnNodeRead, status_code=201)
async def create_node(
    matrix_id: UUID,
    payload: HpnNodeCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnNodeRead:
    return await _call(HpnService(session).create_node(matrix_id, payload))


@router.patch("/matrices/{matrix_id}/nodes/{node_id}", response_model=HpnNodeRead)
async def update_node(
    matrix_id: UUID,
    node_id: UUID,
    payload: HpnNodeUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnNodeRead:
    return await _call(HpnService(session).update_node(matrix_id, node_id, payload))


@router.delete("/matrices/{matrix_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    matrix_id: UUID,
    node_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _call(HpnService(session).delete_node(matrix_id, node_id))
    return Response(status_code=204)


@router.post(
    "/matrices/{matrix_id}/nodes/{node_id}/sources",
    response_model=HpnSourceRead,
    status_code=201,
)
async def add_source(
    matrix_id: UUID,
    node_id: UUID,
    payload: HpnSourceCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnSourceRead:
    return await _call(HpnService(session).add_source(matrix_id, node_id, payload))


@router.delete(
    "/matrices/{matrix_id}/nodes/{node_id}/sources/{source_id}", status_code=204
)
async def delete_source(
    matrix_id: UUID,
    node_id: UUID,
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _call(HpnService(session).delete_source(matrix_id, node_id, source_id))
    return Response(status_code=204)


@router.post(
    "/matrices/{matrix_id}/relations", response_model=HpnRelationRead, status_code=201
)
async def create_relation(
    matrix_id: UUID,
    payload: HpnRelationCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnRelationRead:
    return await _call(HpnService(session).create_relation(matrix_id, payload))


@router.patch(
    "/matrices/{matrix_id}/relations/{relation_id}", response_model=HpnRelationRead
)
async def update_relation(
    matrix_id: UUID,
    relation_id: UUID,
    payload: HpnRelationUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnRelationRead:
    return await _call(
        HpnService(session).update_relation(matrix_id, relation_id, payload)
    )


@router.delete("/matrices/{matrix_id}/relations/{relation_id}", status_code=204)
async def delete_relation(
    matrix_id: UUID,
    relation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _call(HpnService(session).delete_relation(matrix_id, relation_id))
    return Response(status_code=204)
