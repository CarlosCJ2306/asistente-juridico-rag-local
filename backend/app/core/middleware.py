"""Middleware HTTP mínimo para trazabilidad técnica de solicitudes."""

import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.Log import log_exception, log_info
from app.core.security_logging import sanitize_path


def _safe_route_path(request: Request) -> str:
    """Usa la plantilla de ruta o neutraliza UUID sin registrar parámetros."""

    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template.startswith("/"):
        return template
    return sanitize_path(request.url.path)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Asigna un identificador y registra metadatos no sensibles."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_exception(
                "Error no controlado durante la solicitud",
                method=request.method,
                path=_safe_route_path(request),
                request_id=request_id,
                duration_ms=duration_ms,
                exception_type=type(exc).__name__,
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        log_info(
            "Solicitud HTTP completada",
            method=request.method,
            path=_safe_route_path(request),
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
