"""API JSON de solo lectura para la proyección estructural HPN."""

import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.hpn import hpn_http_error
from app.core.Log import log_info, log_warning
from app.core.exceptions import GraphError, HpnError
from app.database.session import get_db_session
from app.schemas.hpn_graph import HpnGraphProjection
from app.services.hpn_graph_service import HpnGraphService
from app.visualization.hpn_pyvis_renderer import HpnPyvisRenderer


router = APIRouter(prefix="/hpn", tags=["hpn-graph"])
_GRAPH_ROUTE_TEMPLATE = "/api/hpn/matrices/{matrix_id}/graph"
_GRAPH_EXPORT_ROUTE_TEMPLATE = "/api/hpn/matrices/{matrix_id}/graph/export"


def _graph_http_error(error: GraphError) -> HTTPException:
    """Convierte únicamente códigos estructurales conocidos en respuestas seguras."""

    error_mapping = {
        "GRAPH_DEPENDENCY_NOT_AVAILABLE": 503,
        "GRAPH_TOO_LARGE": 413,
        "GRAPH_RELATION_INVALID": 409,
        "GRAPH_SOURCE_STATUS_INVALID": 409,
        "GRAPH_RENDER_FAILED": 500,
        "GRAPH_BUILD_FAILED": 500,
    }
    public_code = error.code if error.code in error_mapping else "GRAPH_BUILD_FAILED"
    return HTTPException(
        status_code=error_mapping[public_code],
        detail=public_code,
    )


@router.get(
    "/matrices/{matrix_id}/graph",
    response_model=HpnGraphProjection,
    description=(
        "Proyección estructural HPN temporal y de solo lectura. Requiere revisión "
        "profesional y no representa conclusiones jurídicas automáticas."
    ),
    responses={
        404: {"description": "La matriz activa solicitada no existe."},
        409: {"description": "La estructura o las fuentes HPN no son consistentes."},
        413: {
            "description": "La matriz supera los límites estructurales configurados."
        },
        503: {"description": "La dependencia local de proyección no está disponible."},
        500: {"description": "No fue posible construir la proyección estructural."},
    },
)
async def get_matrix_graph(
    matrix_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HpnGraphProjection:
    """Devuelve una proyección HPN temporal, de solo lectura y revisable."""

    started_at = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    try:
        projection = await HpnGraphService(session).project(
            matrix_id,
            request_id=request_id,
        )
        log_info(
            "Proyección HPN HTTP completada",
            operation="hpn_graph_http",
            path=_GRAPH_ROUTE_TEMPLATE,
            result="success",
            node_count=projection.summary.node_count,
            edge_count=projection.summary.edge_count,
            warning_count=len(projection.warnings),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            request_id=request_id,
        )
        return projection
    except HpnError as exc:
        _log_graph_error(
            exc.code,
            request_id,
            started_at,
            operation="hpn_graph_http",
            path=_GRAPH_ROUTE_TEMPLATE,
        )
        raise hpn_http_error(exc) from exc
    except GraphError as exc:
        http_error = _graph_http_error(exc)
        _log_graph_error(
            str(http_error.detail),
            request_id,
            started_at,
            operation="hpn_graph_http",
            path=_GRAPH_ROUTE_TEMPLATE,
        )
        raise http_error from exc


@router.get(
    "/matrices/{matrix_id}/graph/export",
    response_class=HTMLResponse,
    description=(
        "Exportación PyVis local, offline, temporal y de solo lectura de la "
        "estructura HPN. No constituye una conclusión jurídica y requiere "
        "revisión profesional."
    ),
    responses={
        200: {
            "description": "HTML estructural generado completamente en memoria.",
            "content": {"text/html": {}},
        },
        404: {"description": "La matriz activa solicitada no existe."},
        409: {"description": "La estructura o las fuentes HPN no son consistentes."},
        413: {"description": "La red o el HTML superan los límites configurados."},
        503: {"description": "La dependencia local de visualización no está disponible."},
        500: {"description": "No fue posible construir o renderizar la red."},
    },
)
async def export_matrix_graph(
    matrix_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HTMLResponse:
    """Construye una proyección una sola vez y devuelve HTML sin persistirlo."""

    started_at = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    try:
        projection = await HpnGraphService(session).project(
            matrix_id,
            request_id=request_id,
        )
        rendered = await HpnPyvisRenderer().render(projection)
        log_info(
            "Exportación visual HPN completada",
            operation="hpn_graph_export_http",
            path=_GRAPH_EXPORT_ROUTE_TEMPLATE,
            result="success",
            node_count=projection.summary.node_count,
            edge_count=projection.summary.edge_count,
            warning_count=len(projection.warnings),
            html_bytes=rendered.html_bytes,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            request_id=request_id,
        )
        return HTMLResponse(
            content=rendered.html,
            status_code=200,
            headers=_graph_export_headers(rendered.nonce),
        )
    except HpnError as exc:
        _log_graph_error(
            exc.code,
            request_id,
            started_at,
            operation="hpn_graph_export_http",
            path=_GRAPH_EXPORT_ROUTE_TEMPLATE,
        )
        raise hpn_http_error(exc) from exc
    except GraphError as exc:
        http_error = _graph_http_error(exc)
        _log_graph_error(
            str(http_error.detail),
            request_id,
            started_at,
            operation="hpn_graph_export_http",
            path=_GRAPH_EXPORT_ROUTE_TEMPLATE,
        )
        raise http_error from exc


def _graph_export_headers(nonce: str) -> dict[str, str]:
    csp = (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}'; "
        f"style-src 'nonce-{nonce}'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'none'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'self';"
    )
    return {
        "Content-Security-Policy": csp,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": (
            "accelerometer=(), autoplay=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
        ),
        "Content-Disposition": 'inline; filename="legal-graph.html"',
    }


def _log_graph_error(
    code: str,
    request_id: str | None,
    started_at: float,
    *,
    operation: str,
    path: str,
) -> None:
    """Registra solo metadatos del fallo estructural, sin IDs ni contenido HPN."""

    log_warning(
        "Proyección HPN HTTP rechazada",
        operation=operation,
        path=path,
        result="error",
        error_code=code,
        duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        request_id=request_id,
    )
