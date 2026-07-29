"""Manifiesto interno, versionado y estÃ¡tico de convivencia legacy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegacyModuleManifest:
    name: str
    current_routes: tuple[str, ...]
    preserved_capabilities: tuple[str, ...]
    absent_capabilities: tuple[str, ...]
    future_strategy: str


@dataclass(frozen=True, slots=True)
class LegacyTransitionManifest:
    schema_version: int
    modules: tuple[LegacyModuleManifest, ...]
    deprecation_requirements: tuple[str, ...]
    retirement_requirements: tuple[str, ...]


TRANSITION_MANIFEST = LegacyTransitionManifest(
    schema_version=1,
    modules=(
        LegacyModuleManifest(
            name="hpn_global",
            current_routes=("/matrices-hpn", "/matrices-hpn/:matrixId"),
            preserved_capabilities=("manual", "reviewable", "sources", "global"),
            absent_capabilities=("case_id", "case_versions", "automatic_assignment"),
            future_strategy="explicit_human_assignment_or_migration",
        ),
        LegacyModuleManifest(
            name="legal_network_global",
            current_routes=("/legal-network", "/legal-network/:matrixId"),
            preserved_capabilities=("derived", "networkx", "pyvis_read_only", "rebuildable"),
            absent_capabilities=("case_id", "case_metrics", "simulations", "source_of_truth"),
            future_strategy="derive_from_a_selected_case_hpn_version",
        ),
    ),
    deprecation_requirements=(
        "case_domain", "equivalent_routes", "crud_review_source_network_export_parity",
        "human_assignment_or_migration", "legacy_view", "documentation", "privacy_pc_accessibility", "rollback", "transition_window",
    ),
    retirement_requirements=("all_deprecation_requirements", "completed_transition_window"),
)
