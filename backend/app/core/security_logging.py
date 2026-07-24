"""Reducción de riesgo al incorporar contexto estructurado en los logs."""

from collections.abc import Mapping, Sequence
from typing import Any


SENSITIVE_KEYS = frozenset(
    {"password", "token", "authorization", "cookie", "secret", "api_key"}
)
MASKED_VALUE = "***REDACTED***"


def is_sensitive_key(key: str) -> bool:
    """Indica si una clave puede contener credenciales o secretos."""

    normalized = key.lower().replace("-", "_")
    return any(sensitive in normalized for sensitive in SENSITIVE_KEYS)


def mask_sensitive_value(value: Any) -> str:
    """Sustituye cualquier valor sensible por una marca constante."""

    del value
    return MASKED_VALUE


def sanitize_log_data(data: Any) -> Any:
    """Sanitiza recursivamente estructuras antes de enviarlas al logger."""

    if isinstance(data, Mapping):
        return {
            str(key): (
                mask_sensitive_value(value)
                if is_sensitive_key(str(key))
                else sanitize_log_data(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, (bytes, bytearray, memoryview)):
        return "<binary-content-omitted>"
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return [sanitize_log_data(item) for item in data]
    return data
