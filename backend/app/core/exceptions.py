"""Manejadores globales de excepciones."""

from fastapi import Request
from fastapi.responses import ORJSONResponse

from app.core.Log import log_error
from app.core.security_logging import sanitize_path


class HpnError(RuntimeError):
    """Error HPN estable que nunca transporta contenido jurídico."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
) -> ORJSONResponse:
    """Oculta detalles internos y devuelve una respuesta trazable."""

    request_id = getattr(request.state, "request_id", None)
    log_error(
        "La solicitud terminó con un error interno",
        request_id=request_id,
        path=sanitize_path(request.url.path),
        exception_type=type(exception).__name__,
    )
    return ORJSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id} if request_id else None,
    )
