"""Punto de entrada de la aplicación FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.Log import (
    log_critical,
    log_documentation,
    log_info,
    log_success,
)
from app.core.config import settings
from app.core.exceptions import unhandled_exception_handler
from app.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Registra los eventos esenciales del ciclo de vida."""

    log_info("Iniciando backend", app_env=settings.app_env)
    try:
        log_documentation(
            "Configuración del backend cargada correctamente",
            api_prefix=settings.api_prefix,
        )
        log_success("Backend disponible", service="asistente-juridico-backend")
        yield
    except Exception as exc:
        log_critical(
            "Error durante la inicialización o ejecución del backend",
            exc_info=True,
            exception_type=type(exc).__name__,
        )
        raise
    finally:
        log_info("Apagando backend")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(api_router, prefix=settings.api_prefix)
