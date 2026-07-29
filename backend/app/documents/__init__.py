"""Fachada pública pequeña del dominio documental existente."""

from app.documents.public import (
    DocumentBatch,
    DocumentCatalogFacade,
    DocumentExtractionFacade,
)
from app.schemas.document import DocumentRead, ExtractionSummary
from app.services.document_extraction_service import DocumentExtractionError

__all__ = [
    "DocumentBatch",
    "DocumentCatalogFacade",
    "DocumentExtractionFacade",
    "DocumentExtractionError",
    "DocumentRead",
    "ExtractionSummary",
]
