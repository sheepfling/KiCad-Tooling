"""Blocked design-lint report for unavailable source-bound native evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .design_lint_pcb_coverage_policy import (
    PcbInputCoveragePolicyState,
    PcbMappedCoveragePolicyState,
)
from .design_lint_rule_models import DesignLintRuleCatalog
from .models import (
    ConnectorReturnDistributionCoverageReport,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    PcbKeepoutCoverageReport,
    RcFilterCoverageReport,
    Stm32PinMapCoverageReport,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
)
from .pcb_track_width_models import PcbTrackWidthCoverageReport


@dataclass(frozen=True)
class DesignLintMissingEvidenceInput:
    """Inputs already normalized for a report that cannot inspect a netlist."""

    project_id: str
    coach: ContractCoachReport
    policy: DesignLintPolicy
    catalog: DesignLintRuleCatalog
    stm32_pin_map_coverage: Stm32PinMapCoverageReport
    pcb_input_coverage: PcbInputCoveragePolicyState
    pcb_mapped_coverage: PcbMappedCoveragePolicyState


def missing_evidence_report(data: DesignLintMissingEvidenceInput) -> DesignLintReport:
    """Describe each configured review that lacks the native evidence it needs."""
    policy = data.policy
    coach = data.coach
    pcb_input = data.pcb_input_coverage
    pcb_mapped = data.pcb_mapped_coverage
    rc_filter_coverage = (
        RcFilterCoverageReport(
            status="BLOCKED",
            issue="Source-bound native netlist evidence is unavailable for RC filter review",
        )
        if policy.rc_filter_map is not None
        else RcFilterCoverageReport()
    )
    connector_return_distribution_coverage = (
        ConnectorReturnDistributionCoverageReport(
            status="BLOCKED",
            issue=(
                "Source-bound native netlist evidence is unavailable for connector "
                "return-distribution review"
            ),
        )
        if policy.connector_return_distribution_map is not None
        else ConnectorReturnDistributionCoverageReport()
    )
    pcb_decoupling_coverage = (
        PcbDecouplingCoverageReport(
            status="BLOCKED",
            issue="Source-bound native netlist evidence is unavailable for PCB decoupling review",
        )
        if policy.pcb_decoupling_map is not None
        else PcbDecouplingCoverageReport()
    )
    pcb_track_width_coverage = (
        PcbTrackWidthCoverageReport(
            status="BLOCKED",
            issue="Source-bound native PCB geometry is unavailable for track-width review",
        )
        if policy.pcb_track_width_map is not None
        else PcbTrackWidthCoverageReport()
    )
    loop_map = pcb_mapped.switching_loop_map
    loop_mode = pcb_mapped.switching_loop_mode
    if loop_map is None:
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport()
    elif loop_mode == "off":
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="DISABLED", mode=loop_mode
        )
    else:
        pcb_switching_loop_coverage = PcbSwitchingLoopCoverageReport(
            status="BLOCKED",
            mode=loop_mode,
            map_sha256=hashlib.sha256(loop_map.model_dump_json().encode("utf-8")).hexdigest(),
            issue=(
                "Source-bound native PCB stack and copper evidence is unavailable for "
                "switching-loop review"
            ),
        )
    if policy.pcb_differential_pair_rule_map is None:
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport()
    elif pcb_mapped.differential_pair_mode == "off":
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="DISABLED",
            mode=pcb_mapped.differential_pair_mode,
            map_sha256=pcb_mapped.differential_pair_map_sha256,
        )
    else:
        pcb_differential_pair_coverage = PcbDifferentialPairRuleCoverageReport(
            status="BLOCKED",
            mode=pcb_mapped.differential_pair_mode,
            map_sha256=pcb_mapped.differential_pair_map_sha256,
            issue=(
                "Source-bound native DRC evidence is unavailable for differential-pair "
                "rule coverage"
            ),
        )
    missing_evidence_issues = coach.issues or ("Source-bound netlist evidence is unavailable",)
    if policy.component_role_map is not None:
        missing_evidence_issues += (
            (
                "The project component role map cannot be checked without source-bound native "
                "netlist evidence."
            ),
        )
    if policy.complementary_pin_function_alias_map is not None:
        missing_evidence_issues += (
            (
                "The project complementary pin-function alias map cannot be checked without "
                "source-bound native netlist evidence."
            ),
        )
    return DesignLintReport(
        status="BLOCKED",
        project_id=data.project_id,
        rule_catalog=data.catalog,
        native_summary=coach.native_summary,
        native_status=coach.native_status,
        rc_filter_coverage=rc_filter_coverage,
        connector_return_distribution=connector_return_distribution_coverage,
        pcb_decoupling=pcb_decoupling_coverage,
        pcb_protection_path=pcb_mapped.protection_path,
        pcb_track_width=pcb_track_width_coverage,
        pcb_reference_plane=pcb_mapped.reference_plane,
        pcb_switching_loop=pcb_switching_loop_coverage,
        pcb_differential_pair_rules=pcb_differential_pair_coverage,
        pcb_signal_path_rules=pcb_input.signal_path,
        pcb_keepout_coverage=pcb_input.keepout or PcbKeepoutCoverageReport(),
        pcb_rf_module_antenna_coverage=(pcb_input.rf_antenna or PcbRfModuleAntennaCoverageReport()),
        stm32_pin_map_coverage=data.stm32_pin_map_coverage,
        issues=missing_evidence_issues,
        next_actions=("Repair the native evidence, then rerun design lint.",),
    )
