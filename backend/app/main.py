"""Punto de entrada de la aplicación FastAPI."""

import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.Log import (
    log_critical,
    log_documentation,
    log_error,
    log_info,
    log_success,
)
from app.core.config import settings
from app.core.exceptions import unhandled_exception_handler
from app.core.middleware import RequestLoggingMiddleware
from app.database.session import database_session_manager
from app.services.document_automation_service import get_document_automation_service
from app.services.embedding_runtime_service import get_embedding_runtime_service


_DISPOSE_SENTINEL_NAME = re.compile(r"\.phase10_dispose_[0-9a-f]{32}\.ok\Z")


def _write_phase10_dispose_sentinel() -> None:
    """Escribe el centinela de validación solo cuando se solicita explícitamente."""

    raw_path = os.getenv("PHASE10_DISPOSE_SENTINEL")
    if not raw_path:
        return
    project_root = Path(__file__).resolve().parents[2]
    database_dir = project_root / "storage" / "database"
    candidate = Path(raw_path)
    if (
        candidate.is_absolute() is False
        or ".." in candidate.parts
        or not database_dir.is_dir()
        or database_dir.is_symlink()
        or candidate.is_symlink()
        or candidate.name == "asistente_juridico.db"
        or not _DISPOSE_SENTINEL_NAME.fullmatch(candidate.name)
        or candidate.resolve(strict=False).parent != database_dir.resolve()
    ):
        raise RuntimeError("PHASE10_DISPOSE_SENTINEL_INVALID")
    temporary = database_dir / f".{candidate.name}.{os.getpid()}.tmp"
    try:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        with temporary.open("x", encoding="ascii", newline="") as stream:
            stream.write("DISPOSED")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, candidate)
    except (OSError, ValueError):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("PHASE10_DISPOSE_SENTINEL_WRITE_FAILED") from None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Registra los eventos esenciales del ciclo de vida."""

    log_info("Iniciando backend", app_env=settings.app_env)
    session_factory_getter = getattr(
        database_session_manager, "get_session_factory", None
    )
    automation = (
        get_document_automation_service(session_factory_getter())
        if callable(session_factory_getter)
        else None
    )
    try:
        log_documentation(
            "Configuración del backend cargada correctamente",
            api_prefix=settings.api_prefix,
        )
        log_success("Backend disponible", service="asistente-juridico-backend")
        if automation is not None:
            await automation.start()
        yield
    except Exception as exc:
        log_critical(
            "Error durante la inicialización o ejecución del backend",
            exc_info=True,
            exception_type=type(exc).__name__,
        )
        raise
    finally:
        if automation is not None:
            await automation.stop()
        await get_embedding_runtime_service().shutdown()
        try:
            await database_session_manager.dispose()
        except Exception:
            log_error("DATABASE_ENGINES_DISPOSE_FAILED", operation="database_shutdown")
            raise RuntimeError("DATABASE_ENGINES_DISPOSE_FAILED") from None
        log_info("DATABASE_ENGINES_DISPOSED", operation="database_shutdown")
        try:
            _write_phase10_dispose_sentinel()
        except Exception:
            log_error(
                "DATABASE_DISPOSE_SENTINEL_WRITE_FAILED",
                operation="database_shutdown_confirmation",
            )
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
