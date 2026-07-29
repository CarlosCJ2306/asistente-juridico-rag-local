"""Errores cerrados de la capa de transición, sin contenido de dominio."""

from __future__ import annotations

from enum import Enum


class TransitionErrorCode(str, Enum):
    DOCUMENT_NOT_FOUND = "TRANSITION_DOCUMENT_NOT_FOUND"
    EXTRACTION_REJECTED = "TRANSITION_EXTRACTION_REJECTED"
    RETRIEVAL_SCOPE_UNSUPPORTED = "TRANSITION_RETRIEVAL_SCOPE_UNSUPPORTED"
    RETRIEVAL_REJECTED = "TRANSITION_RETRIEVAL_REJECTED"
    HPN_NOT_FOUND = "TRANSITION_HPN_NOT_FOUND"
    HPN_REJECTED = "TRANSITION_HPN_REJECTED"
    NETWORK_REJECTED = "TRANSITION_NETWORK_REJECTED"
    DEPENDENCY_ERROR = "TRANSITION_DEPENDENCY_ERROR"


class TransitionAdapterError(RuntimeError):
    """Transporta únicamente código, adaptador y etapa seguros."""

    def __init__(self, code: TransitionErrorCode, *, adapter: str, stage: str) -> None:
        super().__init__(code.value)
        self.code = code
        self.adapter = adapter
        self.stage = stage


class CaseError(RuntimeError):
    """Error estable del núcleo Case sin contenido suministrado por el usuario."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
