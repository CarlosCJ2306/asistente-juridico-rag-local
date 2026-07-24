"""Pruebas de garantías del logging centralizado."""

import json

import pytest

from app.core.Log import LogStep, _safe_json, get_log_file_path, get_logger


class NonSerializable:
    def __str__(self) -> str:
        return "representación-controlada"


def test_get_logger_does_not_duplicate_handlers() -> None:
    first_logger = get_logger()
    initial_handlers = tuple(first_logger.handlers)

    second_logger = get_logger()

    assert second_logger is first_logger
    assert tuple(second_logger.handlers) == initial_handlers


def test_safe_json_supports_non_serializable_values() -> None:
    serialized = _safe_json({"value": NonSerializable()})
    result = json.loads(serialized)

    assert "representación-controlada" in result["value"]


def test_log_step_does_not_suppress_exceptions() -> None:
    with pytest.raises(RuntimeError, match="fallo esperado"):
        with LogStep("prueba de propagación"):
            raise RuntimeError("fallo esperado")


def test_get_log_file_path_is_absolute() -> None:
    assert get_log_file_path().is_absolute()
