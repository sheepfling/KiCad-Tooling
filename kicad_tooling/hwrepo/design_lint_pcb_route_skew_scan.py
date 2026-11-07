"""Attach mapped route-skew measurements to source-bound PCB scan evidence."""

from __future__ import annotations

from typing import Literal

from .contract_coach_models import ContractCoachReport
from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence
from .design_lint_policy_models import DesignLintPolicy
from .model_primitives import Digest
from .pcb_differential_pair_route_skew import measure_differential_pair_route_skew
from .pcb_drc_models import PcbSignalPathRuleCoverageReport, PcbSignalPathRuleMap

RouteSkewMode = Literal["review", "block", "off"]


def route_skew_requested(requirements: PcbSignalPathRuleMap | None) -> bool:
    """Return whether the project map declares at least one exact path bundle."""
    return requirements is not None and bool(requirements.bundles)


def route_skew_enabled(policy: DesignLintPolicy) -> bool:
    """Return whether the current project policy requests native route measurement."""
    requirements = policy.pcb_signal_path_rule_map
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_route_skew"),
        None,
    )
    mode: RouteSkewMode = "review" if override is None else override.mode
    return route_skew_requested(requirements) and mode != "off"


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
    if not route_skew_enabled(policy) or requirements is None:
        return report
    override = next(
        (item for item in policy.rules if item.rule_id == "pcb.differential_pair_route_skew"),
        None,
    )
    mode: RouteSkewMode = "review" if override is None else override.mode
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
    return report.model_copy(update={"route_skew": coverage})
