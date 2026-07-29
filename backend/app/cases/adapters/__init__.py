"""Adaptadores de transición inactivos; no se registran en runtime."""

from app.cases.adapters.legacy import (
    DocumentAccessAdapter,
    DocumentExtractionAdapter,
    LegacyHpnAdapter,
    LegacyLegalNetworkAdapter,
    ScopedRetrievalAdapter,
    TransitionAdapters,
    build_transition_adapters,
)

__all__ = [
    "DocumentAccessAdapter",
    "DocumentExtractionAdapter",
    "LegacyHpnAdapter",
    "LegacyLegalNetworkAdapter",
    "ScopedRetrievalAdapter",
    "TransitionAdapters",
    "build_transition_adapters",
]
