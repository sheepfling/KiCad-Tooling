"""Normalize project evidence and policy before theme-specific lint scans."""

from __future__ import annotations

import hashlib
from typing import Literal

from .bus_signal_pairs import (
    resolve_complementary_pin_function_aliases,
)
from .component_roles import resolve_component_role_map
from .design_lint_catalog import rule_catalog
from .design_lint_component_coverage import resolve_component_map_coverage
from .design_lint_evaluation_types import (
    DesignLintEvaluationPreparation,
    DesignLintEvaluationPreparationResult,
    DesignLintEvaluationRequest,
    DesignLintResolvedCoverage,
)
from .design_lint_missing_evidence import (
    DesignLintMissingEvidenceInput,
    missing_evidence_report,
)
from .design_lint_pcb_coverage_policy import (
    normalize_pcb_input_coverage_policy,
    normalize_pcb_mapped_coverage_policy,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_schematic_coverage import (
    SCHEMATIC_GEOMETRY_RULE_IDS,
    schematic_geometry_coverage,
)
from .design_lint_stm32_coverage import resolve_stm32_pin_map_coverage
from .models import (
    DesignLintReport,
    ExternalProtectionCoverageReport,
    I2cPullupHeuristicCoverage,
    SchematicGeometryCoverage,
    SchematicGeometryRuleId,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_track_width_models import PcbTrackWidthCoverageReport


def prepare_evaluation(
    request: DesignLintEvaluationRequest,
) -> DesignLintEvaluationPreparationResult:
    """Resolve coverage states, reject stale inputs, and validate required evidence."""
    coach = request.coach
    policy = request.policy
    catalog = rule_catalog()
    input_pcb_coverage = normalize_pcb_input_coverage_policy(
        policy,
        pcb_signal_path_coverage=request.pcb_signal_path_coverage,
        pcb_keepout_coverage=request.pcb_keepout_coverage,
        pcb_rf_module_antenna_coverage=request.pcb_rf_module_antenna_coverage,
    )
    if request.i2c_pullup_heuristic_coverage is not None:
        i2c_coverage = request.i2c_pullup_heuristic_coverage
        coverage_issue = (
            i2c_coverage.issue
            if i2c_coverage.status == "BLOCKED"
            else "I2C pull-up coverage uses a different or unavailable native netlist hash."
            if i2c_coverage.entries and i2c_coverage.netlist_sha256 != coach.netlist_sha256
            else None
        )
        if coverage_issue is not None:
            blocked_coverage = I2cPullupHeuristicCoverage(
                status="BLOCKED",
                source_path=i2c_coverage.source_path,
                source_sha256=i2c_coverage.source_sha256,
                issue=coverage_issue,
            )
            return DesignLintEvaluationPreparationResult(
                report=DesignLintReport(
                    status="BLOCKED",
                    project_id=request.project_id,
                    source_hashes=coach.source_hashes,
                    netlist_sha256=coach.netlist_sha256,
                    native_summary=coach.native_summary,
                    native_status=coach.native_status,
                    rule_catalog=catalog,
                    i2c_pullup_heuristic_coverage=blocked_coverage,
                    pcb_signal_path_rules=input_pcb_coverage.signal_path,
                    pcb_keepout_coverage=input_pcb_coverage.keepout,
                    pcb_rf_module_antenna_coverage=input_pcb_coverage.rf_antenna,
                    issues=(coverage_issue,),
                    next_actions=(
                        "Recreate I2C pull-up coverage from the current native netlist and contract.",
                    ),
                )
            )

    stm32_pin_map_coverage, source_hashes = resolve_stm32_pin_map_coverage(
        coach,
        policy,
        request.stm32_pin_map_coverage,
    )
    mapped_pcb_coverage = normalize_pcb_mapped_coverage_policy(
        policy,
        pcb_differential_pair_coverage=request.pcb_differential_pair_coverage,
        pcb_switching_loop_coverage=request.pcb_switching_loop_coverage,
        pcb_reference_plane_coverage=request.pcb_reference_plane_coverage,
        pcb_protection_path_coverage=request.pcb_protection_path_coverage,
    )
    if coach.status != "READY_FOR_REVIEW" or coach.observed is None:
        return DesignLintEvaluationPreparationResult(
            report=missing_evidence_report(
                DesignLintMissingEvidenceInput(
                    project_id=request.project_id,
                    coach=coach,
                    policy=policy,
                    catalog=catalog,
                    stm32_pin_map_coverage=stm32_pin_map_coverage,
                    pcb_input_coverage=input_pcb_coverage,
                    pcb_mapped_coverage=mapped_pcb_coverage,
                )
            )
        )

    component_role_resolution = resolve_component_role_map(
        coach.observed, policy.component_role_map
    )
    complementary_alias_resolution = resolve_complementary_pin_function_aliases(
        coach.observed, policy.complementary_pin_function_alias_map
    )
    geometry_coverage = request.geometry_coverage
    if geometry_coverage is None and request.schematic_geometry is not None:
        overrides = {item.rule_id: item for item in policy.rules}
        rule_modes: dict[SchematicGeometryRuleId, Literal["review", "block", "off"]]
        rule_modes = {
            rule_id: overrides[rule_id].mode if rule_id in overrides else "off"
            for rule_id in SCHEMATIC_GEOMETRY_RULE_IDS
        }
        geometry_coverage = schematic_geometry_coverage(
            request.schematic_geometry, coach.netlist_sha256, rule_modes
        )
    if geometry_coverage is None:
        geometry_coverage = SchematicGeometryCoverage()

    external_protection_coverage = (
        request.external_protection_coverage or ExternalProtectionCoverageReport()
    )
    component_map_coverage = resolve_component_map_coverage(
        policy=policy,
        observed=coach.observed,
        netlist_sha256=coach.netlist_sha256,
        connector_coverage=request.connector_coverage,
        i2c_address_coverage=request.i2c_address_coverage,
        crystal_network_coverage=request.crystal_network_coverage,
        regulator_feedback_coverage=request.regulator_feedback_coverage,
        rc_filter_coverage=request.rc_filter_coverage,
        connector_return_distribution_coverage=request.connector_return_distribution_coverage,
    )
    loop_map = mapped_pcb_coverage.switching_loop_map
    loop_mode = mapped_pcb_coverage.switching_loop_mode
    pair_map = mapped_pcb_coverage.differential_pair_map
    pair_mode = mapped_pcb_coverage.differential_pair_mode
    pair_map_sha256 = mapped_pcb_coverage.differential_pair_map_sha256

    pcb_decoupling_coverage = request.pcb_decoupling_coverage
    if pcb_decoupling_coverage is None:
        pcb_decoupling_coverage = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured decoupling map",
            )
            if policy.pcb_decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
    pcb_track_width_coverage = request.pcb_track_width_coverage
    if pcb_track_width_coverage is None:
        pcb_track_width_coverage = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                issue="Native PCB geometry evidence was not supplied for the configured track-width map",
            )
            if policy.pcb_track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
    pcb_switching_loop_coverage = mapped_pcb_coverage.switching_loop
    if pcb_switching_loop_coverage is None:
        pcb_switching_loop_coverage = (
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=loop_mode,
                map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
                issue="Native PCB geometry evidence was not supplied for the configured switching-loop map",
            )
            if loop_map is not None and loop_mode != "off"
            else PcbSwitchingLoopCoverageReport(status="DISABLED", mode=loop_mode)
            if loop_map is not None
            else PcbSwitchingLoopCoverageReport()
        )
    pcb_differential_pair_coverage = mapped_pcb_coverage.differential_pair
    if pcb_differential_pair_coverage is None:
        pair_map = policy.pcb_differential_pair_rule_map
        if pair_map is None:
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport()
        elif pair_mode == "off":
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="DISABLED", mode=pair_mode, map_sha256=pair_map_sha256
            )
        else:
            pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
                status="BLOCKED",
                mode=pair_mode,
                map_sha256=pair_map_sha256,
                issue="Source-bound native DRC rule evidence was not supplied for the configured pair map",
            )

    overrides = {str(item.rule_id): item for item in policy.rules}
    default_modes: dict[DesignLintRuleId, Literal["review", "block", "off"]] = {
        item.rule_id: item.default_mode for item in catalog.rules
    }
    prepared = DesignLintEvaluationPreparation(
        request=request,
        catalog=catalog,
        source_hashes=source_hashes,
        input_pcb_coverage=input_pcb_coverage,
        mapped_pcb_coverage=mapped_pcb_coverage,
        coverage=DesignLintResolvedCoverage(
            geometry=geometry_coverage,
            i2c_address=component_map_coverage.i2c_address,
            external_protection=external_protection_coverage,
            crystal_network=component_map_coverage.crystal_network,
            regulator_feedback=component_map_coverage.regulator_feedback,
            rc_filter=component_map_coverage.rc_filter,
            connector_return_distribution=component_map_coverage.connector_return_distribution,
            pcb_decoupling=pcb_decoupling_coverage,
            pcb_protection_path=mapped_pcb_coverage.protection_path,
            pcb_track_width=pcb_track_width_coverage,
            pcb_reference_plane=mapped_pcb_coverage.reference_plane,
            pcb_switching_loop=pcb_switching_loop_coverage,
            pcb_differential_pair=pcb_differential_pair_coverage,
            pcb_signal_path=input_pcb_coverage.signal_path,
            pcb_keepout=input_pcb_coverage.keepout,
            pcb_rf_module_antenna=input_pcb_coverage.rf_antenna,
            stm32_pin_map=stm32_pin_map_coverage,
            control_input_bias=request.control_input_bias_coverage,
            i2c_pullup_heuristic=request.i2c_pullup_heuristic_coverage,
        ),
        component_role_resolution=component_role_resolution,
        complementary_alias_resolution=complementary_alias_resolution,
        overrides=overrides,
        ignores={str(item.fingerprint): item for item in policy.ignores},
        default_modes=default_modes,
    )
    return DesignLintEvaluationPreparationResult(prepared=prepared)
