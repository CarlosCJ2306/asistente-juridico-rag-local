"""Logging centralizado del Asistente Jurídico RAG Local.

Autor: Carlos Andrés Jiménez Sarmiento (CJ).
Proyecto: Asistente Jurídico RAG Local.
"""

import inspect
import json
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from app.core.config import settings
from app.core.security_logging import sanitize_log_data


LOGGER_NAME = "asistente_juridico_backend"
DOC_LEVEL = 15
SUCCESS_LEVEL = 25
_CONFIGURED_MARKER = "_asistente_juridico_logger_configured"

logging.addLevelName(DOC_LEVEL, "DOC")
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _safe_json(value: Any) -> str:
    """Serializa contexto de manera segura, incluso con objetos no estándar."""

    sanitized = sanitize_log_data(value)
    return json.dumps(
        sanitized,
        ensure_ascii=False,
        sort_keys=True,
        default=lambda item: f"<{type(item).__name__}: {item!s}>",
    )


def _format_message(message: str, context: dict[str, Any]) -> str:
    if not context:
        return message
    return f"{message} | context={_safe_json(context)}"


def _configure_logger(logger: logging.Logger) -> None:
    if getattr(logger, _CONFIGURED_MARKER, False):
        return

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
    )

    if settings.log_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if settings.log_to_file:
        log_file_path = settings.log_file_path
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    setattr(logger, _CONFIGURED_MARKER, True)


def get_logger() -> logging.Logger:
    """Obtiene el logger único de la aplicación sin duplicar handlers."""

    logger = logging.getLogger(LOGGER_NAME)
    _configure_logger(logger)
    return logger


def _log(level: int, message: str, *, exc_info: bool = False, **context: Any) -> None:
    get_logger().log(
        level,
        _format_message(message, context),
        exc_info=exc_info,
        stacklevel=3,
    )


def log_debug(message: str, **context: Any) -> None:
    _log(logging.DEBUG, message, **context)


def log_info(message: str, **context: Any) -> None:
    _log(logging.INFO, message, **context)


def log_success(message: str, **context: Any) -> None:
    _log(SUCCESS_LEVEL, message, **context)


def log_warning(message: str, **context: Any) -> None:
    _log(logging.WARNING, message, **context)


def log_error(message: str, **context: Any) -> None:
    _log(logging.ERROR, message, **context)


def log_critical(message: str, *, exc_info: bool = False, **context: Any) -> None:
    _log(logging.CRITICAL, message, exc_info=exc_info, **context)


def log_exception(message: str, **context: Any) -> None:
    """Registra el mensaje junto con la traza completa de la excepción activa."""

    _log(logging.ERROR, message, exc_info=True, **context)


def log_documentation(message: str, **context: Any) -> None:
    _log(DOC_LEVEL, message, **context)


def _get_caller_location() -> tuple[str, int]:
    """Localiza el primer frame externo a este módulo."""

    current_file = Path(__file__).resolve()
    frame = inspect.currentframe()
    try:
        while frame is not None:
            frame_file = Path(frame.f_code.co_filename).resolve()
            if frame_file != current_file:
                return frame_file.name, frame.f_lineno
            frame = frame.f_back
    finally:
        del frame
    return "unknown", 0


def log_step(step: str, **context: Any) -> None:
    """Registra un hito e identifica correctamente su llamada externa."""

    caller_file, caller_line = _get_caller_location()
    log_info(
        step,
        caller_file=caller_file,
        caller_line=caller_line,
        **context,
    )


def get_log_file_path() -> Path:
    """Expone la ruta absoluta configurada para el archivo de log."""

    return settings.log_file_path


class LogStep:
    """Context manager para registrar inicio, fin y fallo de una operación."""

    def __init__(self, step: str, **context: Any) -> None:
        self.step = step
        self.context = context
        self.started_at = 0.0

    def __enter__(self) -> Self:
        self.started_at = time.perf_counter()
        log_step(f"Inicio: {self.step}", **self.context)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        duration_ms = round((time.perf_counter() - self.started_at) * 1000, 2)
        if exc_type is None:
            log_success(
                f"Finalizado: {self.step}",
                duration_ms=duration_ms,
                **self.context,
            )
        else:
            log_exception(
                f"Falló: {self.step}",
                duration_ms=duration_ms,
                exception_type=exc_type.__name__,
                **self.context,
            )
        return False
