"""Fachada pública de recuperación existente."""

from app.retrieval.public import (
    HybridSearchRequest,
    HybridSearchResponse,
    ScopedHybridRetrievalFacade,
)
from app.schemas.text_search import TextMatchMode

__all__ = [
    "HybridSearchRequest",
    "HybridSearchResponse",
    "ScopedHybridRetrievalFacade",
    "TextMatchMode",
]
