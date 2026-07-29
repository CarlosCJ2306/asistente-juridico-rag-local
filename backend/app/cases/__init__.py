"""Contratos inactivos para la transición al futuro dominio de casos.

Importar este paquete no registra routers, abre persistencia ni inicializa modelos.
"""

from app.cases.contracts import (
    DocumentBatchReference,
    EvidenceReference,
    EvidenceScope,
    FutureAssignmentOutcome,
    ExtractionReference,
    LegacyHpnReference,
    LegacyAssignmentDecision,
    LegacyCompatibilityReasonCode,
    LegacyCompatibilityState,
    LegacyDeprecationDecision,
    LegacyDeprecationReasonCode,
    LegacyNetworkReference,
    LegacySourceHealth,
    PublicDocumentReference,
    ScopedRetrievalQuery,
    ScopedRetrievalResult,
    TextMatchModeValue,
    TransitionWarningCode,
)
from app.cases.legacy_compatibility import (
    LegacyDeprecationConditions,
    classify_current_hpn,
    classify_current_network,
    evaluate_future_manual_assignment,
    evaluate_legacy_deprecation,
)
from app.cases.transition_manifest import TRANSITION_MANIFEST, LegacyModuleManifest, LegacyTransitionManifest
from app.cases.errors import TransitionAdapterError, TransitionErrorCode
from app.cases.ports import (
    DocumentAccessPort,
    DocumentExtractionPort,
    LegacyHpnPort,
    LegacyLegalNetworkPort,
    ScopedRetrievalPort,
)

__all__ = [
    "DocumentAccessPort",
    "DocumentBatchReference",
    "DocumentExtractionPort",
    "EvidenceReference",
    "EvidenceScope",
    "FutureAssignmentOutcome",
    "ExtractionReference",
    "LegacyHpnPort",
    "LegacyHpnReference",
    "LegacyAssignmentDecision",
    "LegacyCompatibilityReasonCode",
    "LegacyCompatibilityState",
    "LegacyDeprecationConditions",
    "LegacyDeprecationDecision",
    "LegacyDeprecationReasonCode",
    "LegacyLegalNetworkPort",
    "LegacyModuleManifest",
    "LegacyNetworkReference",
    "LegacySourceHealth",
    "LegacyTransitionManifest",
    "PublicDocumentReference",
    "ScopedRetrievalPort",
    "ScopedRetrievalQuery",
    "ScopedRetrievalResult",
    "TextMatchModeValue",
    "TransitionAdapterError",
    "TransitionErrorCode",
    "TRANSITION_MANIFEST",
    "TransitionWarningCode",
    "classify_current_hpn",
    "classify_current_network",
    "evaluate_future_manual_assignment",
    "evaluate_legacy_deprecation",
]
