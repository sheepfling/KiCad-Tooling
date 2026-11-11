"""Attach mapped route-skew measurements to source-bound PCB scan evidence."""

from __future__ import annotations

from typing import Literal

from .contract_coach_models import ContractCoachReport
from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .design_lint_policy_models import DesignLintPolicy
from .model_primitives import Digest
from .netlist_contract_models import NetlistContract
from .pcb_differential_pair_reference_via_models import (
    PcbDifferentialPairReferenceViaReport,
)
from .pcb_differential_pair_reference_via_stitching import (
    ReferenceViaMode,
    measure_differential_pair_reference_via_stitching,
)
from .pcb_differential_pair_route_skew import measure_differential_pair_route_skew
from .pcb_drc_models import PcbSignalPathRuleCoverageReport
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap

RouteSkewMode = Literal["review", "block", "off"]


def route_skew_requested(requirements: PcbSignalPathRuleMap | None) -> bool:
    """Return whether the project map declares a bundle with a skew maximum."""
    return requirements is not None and any(
        item.max_skew is not None for item in requirements.bundles
    )


def route_skew_enabled(policy: DesignLintPolicy) -> bool:
    """Return whether the current project policy requests native route measurement."""
    requirements = policy.pcb_signal_path_rule_map
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_route_skew"),
        None,
    )
    mode: RouteSkewMode = "review" if override is None else override.mode
    return route_skew_requested(requirements) and mode != "off"


def route_skew_policy_mode(policy: DesignLintPolicy) -> RouteSkewMode:
    """Return the exact project mode for the skew rule without shared-route fallback."""
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_route_skew"),
        None,
    )
    return "review" if override is None else override.mode


def route_layer_transition_enabled(policy: DesignLintPolicy) -> bool:
    """Return whether mapped pair layer-profile review is enabled by project policy."""
    requirements = policy.pcb_signal_path_rule_map
    override = next(
        (
            item
            for item in policy.rules
            if item.rule_id == "pcb.differential_pair_route_layer_mismatch"
        ),
        None,
    )
    mode: RouteSkewMode = "review" if override is None else override.mode
    return route_skew_requested(requirements) and mode != "off"


def reference_via_stitching_requested(requirements: PcbSignalPathRuleMap | None) -> bool:
    """Return whether any authored pair bundle opts into reference-via review."""
    return requirements is not None and any(
        item.reference_net is not None and item.max_reference_via_distance_nm is not None
        for item in requirements.bundles
    )


def reference_via_stitching_mode(policy: DesignLintPolicy) -> ReferenceViaMode:
    """Return the project's configured mode for pair reference-via review."""
    override = next(
        (
            item
            for item in policy.rules
            if item.rule_id == "pcb.differential_pair_reference_via_stitching"
        ),
        None,
    )
    return "review" if override is None else override.mode


def reference_via_stitching_enabled(policy: DesignLintPolicy) -> bool:
    """Return whether configured pair reference-via checks are enabled."""
    return reference_via_stitching_requested(policy.pcb_signal_path_rule_map) and (
        reference_via_stitching_mode(policy) != "off"
    )


def route_measurement_enabled(policy: DesignLintPolicy) -> bool:
    """Return whether either mapped pair-route rule needs native route geometry."""
    return (
        route_skew_enabled(policy)
        or route_layer_transition_enabled(policy)
        or reference_via_stitching_enabled(policy)
    )


def route_measurement_mode(policy: DesignLintPolicy) -> RouteSkewMode:
    """Keep shared route evidence available when only layer-profile review is active."""
    mode = route_skew_policy_mode(policy)
    return (
        "review"
        if mode == "off"
        and (route_layer_transition_enabled(policy) or reference_via_stitching_enabled(policy))
        else mode
    )


def measure_route_skew_for_geometry_scan(
    report: PcbSignalPathRuleCoverageReport,
    *,
    policy: DesignLintPolicy,
    coach: ContractCoachReport,
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: Digest,
) -> PcbSignalPathRuleCoverageReport:
    """Measure route skew from the one native snapshot captured for PCB geometry."""
    requirements = policy.pcb_signal_path_rule_map
    if requirements is None:
        return report
    stitching_requested = reference_via_stitching_requested(requirements)
    stitching_mode = reference_via_stitching_mode(policy)
    if not route_measurement_enabled(policy):
        if stitching_requested and stitching_mode == "off":
            disabled = measure_differential_pair_reference_via_stitching(
                requirements,
                coach.observed if coach.observed is not None else _empty_netlist(),
                evidence,
                coach.source_hashes,
                netlist_sha256,
                "off",
            )
            return report.model_copy(update={"reference_via_stitching": disabled})
        return report
    mode = route_measurement_mode(policy)
    if coach.observed is None:
        raise ValueError("Source-bound schematic netlist is unavailable for route-skew analysis")
    coverage = measure_differential_pair_route_skew(
        requirements,
        coach.observed,
        evidence,
        coach.source_hashes,
        netlist_sha256,
        mode,
    )
    stitching = (
        measure_differential_pair_reference_via_stitching(
            requirements,
            coach.observed,
            evidence,
            coach.source_hashes,
            netlist_sha256,
            stitching_mode,
        )
        if stitching_requested
        else PcbDifferentialPairReferenceViaReport()
    )
    return report.model_copy(
        update={
            "route_skew": coverage,
            "reference_via_stitching": stitching if stitching_requested else None,
        }
    )


def _empty_netlist() -> NetlistContract:
    """Supply an inert input when constructing disabled, unmeasured coverage."""
    return NetlistContract(components={}, nets={})
