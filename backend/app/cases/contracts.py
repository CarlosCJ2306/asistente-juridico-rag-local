"""DTO inmutables y mínimos del paquete de casos todavía inactivo."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class TransitionWarningCode(str, Enum):
    DOCUMENT_NOT_RAG_ELIGIBLE = "DOCUMENT_NOT_RAG_ELIGIBLE"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MATRIX_ARCHIVED = "MATRIX_ARCHIVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class LegacyCompatibilityState(str, Enum):
    """ClasificaciÃ³n interna de recursos durante la transiciÃ³n a Case."""

    CURRENT_GLOBAL = "current_global"
    CASE_READY = "case_ready"
    CASE_BOUND = "case_bound"
    UNASSIGNED_LEGACY = "unassigned_legacy"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class LegacySourceHealth(str, Enum):
    VALID = "valid"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class FutureAssignmentOutcome(str, Enum):
    ELIGIBLE_FOR_FUTURE_MANUAL_ASSIGNMENT = "eligible_for_future_manual_assignment"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"
    UNSUPPORTED = "unsupported"


class LegacyCompatibilityReasonCode(str, Enum):
    MATRIX_ARCHIVED = "LEGACY_MATRIX_ARCHIVED"
    MATRIX_REVIEW_REQUIRED = "LEGACY_MATRIX_REVIEW_REQUIRED"
    SOURCE_STALE = "LEGACY_SOURCE_STALE"
    SOURCE_UNAVAILABLE = "LEGACY_SOURCE_UNAVAILABLE"
    NETWORK_UNAVAILABLE = "LEGACY_NETWORK_UNAVAILABLE"
    STRUCTURAL_INTEGRITY_INVALID = "LEGACY_STRUCTURAL_INTEGRITY_INVALID"
    COMPATIBILITY_UNSUPPORTED = "LEGACY_COMPATIBILITY_UNSUPPORTED"
    TRANSITION_PHASE_NOT_READY = "LEGACY_TRANSITION_PHASE_NOT_READY"


class LegacyDeprecationReasonCode(str, Enum):
    CASE_DOMAIN_UNAVAILABLE = "LEGACY_CASE_DOMAIN_UNAVAILABLE"
    EQUIVALENT_ROUTES_UNAVAILABLE = "LEGACY_EQUIVALENT_ROUTES_UNAVAILABLE"
    PARITY_INCOMPLETE = "LEGACY_PARITY_INCOMPLETE"
    MIGRATION_UNAVAILABLE = "LEGACY_MIGRATION_UNAVAILABLE"
    LEGACY_VIEW_REQUIRED = "LEGACY_VIEW_REQUIRED"
    DOCUMENTATION_INCOMPLETE = "LEGACY_DOCUMENTATION_INCOMPLETE"
    PRIVACY_OR_ACCESSIBILITY_UNVALIDATED = "LEGACY_PRIVACY_OR_ACCESSIBILITY_UNVALIDATED"
    ROLLBACK_UNVALIDATED = "LEGACY_ROLLBACK_UNVALIDATED"
    TRANSITION_WINDOW_UNDOCUMENTED = "LEGACY_TRANSITION_WINDOW_UNDOCUMENTED"
    TRANSITION_PHASE_NOT_READY = "LEGACY_TRANSITION_PHASE_NOT_READY"


class TextMatchModeValue(str, Enum):
    ALL_TERMS = "all_terms"
    ANY_TERM = "any_term"
    PHRASE = "phrase"


@dataclass(frozen=True, slots=True)
class PublicDocumentReference:
    document_id: UUID
    display_name: str
    document_type: str
    knowledge_layer: str
    extraction_status: str
    review_status: str
    legal_validity_status: str
    index_status: str
    rag_eligible: bool
    warnings: tuple[TransitionWarningCode, ...] = ()

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("TRANSITION_DOCUMENT_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class DocumentBatchReference:
    items: tuple[PublicDocumentReference, ...]
    missing_document_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ExtractionReference:
    document_id: UUID
    status: str
    total_pages: int | None = None
    total_chunks: int | None = None
    total_characters: int | None = None

    def __post_init__(self) -> None:
        for value in (self.total_pages, self.total_chunks, self.total_characters):
            if value is not None and value < 0:
                raise ValueError("TRANSITION_EXTRACTION_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class EvidenceScope:
    document_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.document_ids or len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("TRANSITION_EVIDENCE_SCOPE_INVALID")


@dataclass(frozen=True, slots=True)
class ScopedRetrievalQuery:
    query: str
    scope: EvidenceScope
    top_k: int = 10
    text_match_mode: TextMatchModeValue = TextMatchModeValue.ALL_TERMS

    def __post_init__(self) -> None:
        if (
            not self.query.strip()
            or len(self.query) > 500
            or self.top_k < 1
            or self.top_k > 100
            or any(unicodedata.category(char).startswith("C") for char in self.query)
        ):
            raise ValueError("TRANSITION_RETRIEVAL_QUERY_INVALID")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    document_id: UUID
    document_name: str
    document_type: str
    knowledge_layer: str
    chunk_index: int
    start_page: int
    end_page: int
    hybrid_score: float
    appeared_in_text: bool
    appeared_in_semantic: bool
    text_rank: int | None
    semantic_rank: int | None

    def __post_init__(self) -> None:
        if (
            not self.document_name.strip()
            or self.chunk_index < 1
            or self.start_page < 1
            or self.end_page < self.start_page
            or not math.isfinite(self.hybrid_score)
            or self.hybrid_score <= 0
        ):
            raise ValueError("TRANSITION_EVIDENCE_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class ScopedRetrievalResult:
    items: tuple[EvidenceReference, ...]
    returned: int
    top_k: int

    def __post_init__(self) -> None:
        if self.returned != len(self.items) or self.returned > self.top_k:
            raise ValueError("TRANSITION_RETRIEVAL_RESULT_INVALID")


@dataclass(frozen=True, slots=True)
class LegacyHpnReference:
    public_matrix_id: UUID
    status: str
    fact_count: int
    evidence_count: int
    norm_count: int
    relation_count: int
    stale_source_count: int
    unavailable_source_count: int
    read_only: bool
    warnings: tuple[TransitionWarningCode, ...]
    display_name: str = "Matriz HPN"
    compatibility_state: LegacyCompatibilityState = LegacyCompatibilityState.CURRENT_GLOBAL
    source_health: LegacySourceHealth = LegacySourceHealth.VALID
    case_assignment_allowed: bool = False
    migration_required: bool = True

    @property
    def matrix_id(self) -> UUID:
        """Compatibilidad interna con el contrato 12D-1; no es una asociaciÃ³n Case."""

        return self.public_matrix_id


@dataclass(frozen=True, slots=True)
class LegacyNetworkReference:
    public_matrix_id: UUID
    node_count: int
    edge_count: int
    disconnected_components: int
    has_directed_cycles: bool
    warning_codes: tuple[str, ...]
    requires_professional_review: bool
    graph_availability: bool = True
    compatibility_state: LegacyCompatibilityState = LegacyCompatibilityState.CURRENT_GLOBAL
    projection_type: str = "networkx_pyvis_read_only"
    migration_required: bool = True

    @property
    def matrix_id(self) -> UUID:
        """Compatibilidad interna con el contrato 12D-1; no es una asociaciÃ³n Case."""

        return self.public_matrix_id


@dataclass(frozen=True, slots=True)
class LegacyAssignmentDecision:
    outcome: FutureAssignmentOutcome
    reason_codes: tuple[LegacyCompatibilityReasonCode, ...]


@dataclass(frozen=True, slots=True)
class LegacyDeprecationDecision:
    deprecation_ready: bool
    retirement_ready: bool
    reason_codes: tuple[LegacyDeprecationReasonCode, ...]
