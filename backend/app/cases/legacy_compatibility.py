"""PolÃ­ticas puras de compatibilidad legacy; no leen ni escriben persistencia."""

from __future__ import annotations

from dataclasses import dataclass

from app.cases.contracts import (
    FutureAssignmentOutcome,
    LegacyAssignmentDecision,
    LegacyCompatibilityReasonCode,
    LegacyCompatibilityState,
    LegacyDeprecationDecision,
    LegacyDeprecationReasonCode,
    LegacyHpnReference,
    LegacyNetworkReference,
    LegacySourceHealth,
    TransitionWarningCode,
)


@dataclass(frozen=True, slots=True)
class LegacyDeprecationConditions:
    case_domain_functional: bool = False
    case_routes_equivalent: bool = False
    crud_parity: bool = False
    review_parity: bool = False
    source_parity: bool = False
    network_parity: bool = False
    export_parity: bool = False
    human_assignment_available: bool = False
    unassigned_legacy_view_available: bool = False
    documentation_updated: bool = False
    privacy_validated: bool = False
    pc_accessibility_validated: bool = False
    rollback_validated: bool = False
    transition_window_documented: bool = False


def classify_current_hpn() -> LegacyCompatibilityState:
    return LegacyCompatibilityState.CURRENT_GLOBAL


def classify_current_network() -> LegacyCompatibilityState:
    return LegacyCompatibilityState.CURRENT_GLOBAL


def evaluate_future_manual_assignment(
    hpn: LegacyHpnReference,
    network: LegacyNetworkReference,
) -> LegacyAssignmentDecision:
    """EvalÃºa solo metadatos ya resumidos, sin asignar ni mutar recursos."""

    reasons: list[LegacyCompatibilityReasonCode] = []
    if hpn.compatibility_state is not LegacyCompatibilityState.CURRENT_GLOBAL:
        reasons.append(LegacyCompatibilityReasonCode.COMPATIBILITY_UNSUPPORTED)
    if network.compatibility_state is not LegacyCompatibilityState.CURRENT_GLOBAL:
        reasons.append(LegacyCompatibilityReasonCode.COMPATIBILITY_UNSUPPORTED)
    if not network.graph_availability:
        reasons.append(LegacyCompatibilityReasonCode.NETWORK_UNAVAILABLE)
    if "GRAPH_RELATION_INVALID" in network.warning_codes:
        reasons.append(LegacyCompatibilityReasonCode.STRUCTURAL_INTEGRITY_INVALID)
    if hpn.source_health is LegacySourceHealth.UNAVAILABLE:
        reasons.append(LegacyCompatibilityReasonCode.SOURCE_UNAVAILABLE)
    if reasons:
        return LegacyAssignmentDecision(FutureAssignmentOutcome.BLOCKED, tuple(dict.fromkeys(reasons)))

    if hpn.source_health is LegacySourceHealth.STALE:
        reasons.append(LegacyCompatibilityReasonCode.SOURCE_STALE)
    if hpn.status == "archived":
        reasons.append(LegacyCompatibilityReasonCode.MATRIX_ARCHIVED)
    if TransitionWarningCode.REVIEW_REQUIRED in hpn.warnings:
        reasons.append(LegacyCompatibilityReasonCode.MATRIX_REVIEW_REQUIRED)
    if reasons:
        return LegacyAssignmentDecision(FutureAssignmentOutcome.REQUIRES_REVIEW, tuple(dict.fromkeys(reasons)))

    return LegacyAssignmentDecision(
        FutureAssignmentOutcome.ELIGIBLE_FOR_FUTURE_MANUAL_ASSIGNMENT,
        (),
    )


def evaluate_legacy_deprecation(
    conditions: LegacyDeprecationConditions,
) -> LegacyDeprecationDecision:
    """12D-3 solo prepara condiciones: ninguna ruta legacy puede deprecarse aÃºn."""

    checks = (
        (conditions.case_domain_functional, LegacyDeprecationReasonCode.CASE_DOMAIN_UNAVAILABLE),
        (conditions.case_routes_equivalent, LegacyDeprecationReasonCode.EQUIVALENT_ROUTES_UNAVAILABLE),
        (conditions.crud_parity and conditions.review_parity and conditions.source_parity and conditions.network_parity and conditions.export_parity, LegacyDeprecationReasonCode.PARITY_INCOMPLETE),
        (conditions.human_assignment_available, LegacyDeprecationReasonCode.MIGRATION_UNAVAILABLE),
        (conditions.unassigned_legacy_view_available, LegacyDeprecationReasonCode.LEGACY_VIEW_REQUIRED),
        (conditions.documentation_updated, LegacyDeprecationReasonCode.DOCUMENTATION_INCOMPLETE),
        (conditions.privacy_validated and conditions.pc_accessibility_validated, LegacyDeprecationReasonCode.PRIVACY_OR_ACCESSIBILITY_UNVALIDATED),
        (conditions.rollback_validated, LegacyDeprecationReasonCode.ROLLBACK_UNVALIDATED),
        (conditions.transition_window_documented, LegacyDeprecationReasonCode.TRANSITION_WINDOW_UNDOCUMENTED),
    )
    reasons = [reason for satisfied, reason in checks if not satisfied]
    reasons.append(LegacyDeprecationReasonCode.TRANSITION_PHASE_NOT_READY)
    return LegacyDeprecationDecision(False, False, tuple(reasons))
