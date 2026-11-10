"""Build PCB coverage defaults when no native geometry scan is required."""

from __future__ import annotations

from typing import Literal, TypeVar

from pydantic import BaseModel

from .design_lint_pcb_coverage_common import PcbRuleMode
from .design_lint_policy_models import DesignLintPolicy
from .discovery import ProjectConfig
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbSignalPathRuleCoverageReport
from .pcb_fiducial_models import PcbFiducialCoverageReport
from .pcb_keepout_models import PcbKeepoutCoverageReport
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_thermal_via_models import PcbThermalViaCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport
from .project_models import ProjectKind

FastPathMode = Literal["not_requested", "disabled"]
ReportT = TypeVar("ReportT", bound=BaseModel)


def pcb_geometry_fast_path_reports(
    config: ProjectConfig,
    policy: DesignLintPolicy,
    *,
    inventory_mode: PcbRuleMode,
    mode: FastPathMode,
) -> tuple[
    PcbDecouplingCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbTrackWidthCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbSwitchingLoopCoverageReport,
    PcbSignalPathRuleCoverageReport,
    PcbKeepoutCoverageReport,
    PcbRfModuleAntennaCoverageReport,
    PcbTouchPadClearanceCoverageReport,
    PcbComponentInventoryCoverageReport,
    PcbThermalViaCoverageReport,
]:
    """Return consistent defaults without allocating native evidence artifacts."""
    overrides = {item.rule_id: item for item in policy.rules}

    def report(report_type: type[ReportT], configured: object, rule_id: str) -> ReportT:
        if mode == "not_requested" or configured is None:
            return report_type()
        override = overrides.get(rule_id)
        rule_mode: PcbRuleMode = "review" if override is None else override.mode
        return report_type(status="DISABLED", mode=rule_mode)

    return (
        report(PcbDecouplingCoverageReport, policy.pcb_decoupling_map, "pcb.decoupling_proximity"),
        report(
            PcbProtectionPathCoverageReport,
            policy.pcb_protection_path_map,
            "pcb.protection_entry_path",
        ),
        report(PcbTrackWidthCoverageReport, policy.pcb_track_width_map, "pcb.minimum_track_width"),
        report(
            PcbReferencePlaneCoverageReport,
            policy.pcb_reference_plane_map,
            "pcb.reference_plane_coverage",
        ),
        report(
            PcbSwitchingLoopCoverageReport,
            policy.pcb_switching_loop_map,
            "pcb.switching_loop_geometry",
        ),
        report(
            PcbSignalPathRuleCoverageReport,
            policy.pcb_signal_path_rule_map,
            "pcb.signal_path_rule_coverage",
        ),
        report(PcbKeepoutCoverageReport, policy.pcb_keepout_map, "pcb.keepout_intent_coverage"),
        report(
            PcbRfModuleAntennaCoverageReport,
            policy.pcb_rf_module_antenna_map,
            "pcb.rf_module_antenna_keepout_coverage",
        ),
        report(
            PcbTouchPadClearanceCoverageReport,
            policy.pcb_touch_pad_clearance_map,
            "pcb.touch_pad_reference_clearance",
        ),
        PcbComponentInventoryCoverageReport(
            status=("DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE"),
            mode=inventory_mode if config.kind is ProjectKind.PCB else None,
            fiducial_coverage=report(
                PcbFiducialCoverageReport,
                policy.pcb_fiducial_map,
                "pcb.fiducial_count",
            ),
        ),
        report(PcbThermalViaCoverageReport, policy.pcb_thermal_via_map, "pcb.thermal_via_coverage"),
    )
