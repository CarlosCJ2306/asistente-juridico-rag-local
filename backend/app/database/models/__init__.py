"""Modelos de persistencia disponibles."""

from app.database.models.document_chunk import DocumentChunk
from app.database.models.document import (
    Document,
    DocumentStatus,
    DocumentType,
    IndexStatus,
    KnowledgeLayer,
    LegalValidityStatus,
    RagEligibilityReason,
    ReviewStatus,
    SourceKind,
)
from app.database.models.document_page import DocumentPage
from app.database.models.document_processing_job import (
    DocumentProcessingJob,
    DocumentProcessingOperation,
    DocumentProcessingState,
)
from app.database.models.hpn import (
    HpnMatrix,
    HpnMatrixStatus,
    HpnNode,
    HpnNodeSource,
    HpnNodeType,
    HpnRelation,
    HpnRelationType,
    HpnReviewStatus,
)
from app.database.models.managed_corpus import ManagedCorpusEntry


__all__ = [
    "Document", "DocumentChunk", "DocumentPage", "DocumentStatus", "DocumentType",
    "IndexStatus", "KnowledgeLayer", "LegalValidityStatus", "RagEligibilityReason",
    "ReviewStatus", "SourceKind",
    "HpnMatrix", "HpnMatrixStatus", "HpnNode", "HpnNodeSource", "HpnNodeType",
    "HpnRelation", "HpnRelationType", "HpnReviewStatus",
    "ManagedCorpusEntry",
    "DocumentProcessingJob", "DocumentProcessingOperation", "DocumentProcessingState",
]
