"""Source-bound native PCB geometry scan orchestration."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .contract_coach_models import ContractCoachReport
from .design_lint_pcb_component_inventory_scan import (
    scan_pcb_component_inventory,
)
from .design_lint_pcb_coverage_common import map_sha256
from .design_lint_pcb_fiducial_scan import blocked_pcb_fiducial_coverage
from .design_lint_pcb_geometry_capture import capture_pcb_geometry_source
from .design_lint_pcb_geometry_fast_paths import pcb_geometry_fast_path_reports
from .design_lint_pcb_geometry_modes import resolve_pcb_geometry_scan_modes
from .design_lint_pcb_layout_coverage import layout_coverage_reports
from .design_lint_pcb_measurement_coverage import measurement_coverage_reports
from .design_lint_pcb_route_skew_scan import (
    measure_route_skew_for_geometry_scan,
)
from .design_lint_pcb_thermal_via_scan import blocked_thermal_via_coverage
from .design_lint_pcb_track_angle_geometry_scan import (
    track_angle_geometry_candidates_for_scan,
    track_angle_geometry_scan_required,
)
from .design_lint_policy_models import DesignLintPolicy
from .design_lint_types import Candidate
from .discovery import ProjectConfig
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprintCoverage
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport, PcbDecouplingMap
from .pcb_drc_models import PcbSignalPathRuleCoverageReport
from .pcb_fiducial_models import PcbFiducialMap
from .pcb_fiducials import evaluate_pcb_fiducials
from .pcb_geometry_receipts import verify_pcb_geometry_receipts
from .pcb_keepout_models import (
    PcbKeepoutCoverageReport,
    PcbKeepoutMap,
)
from .pcb_protection_path_models import (
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
)
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport, PcbReferencePlaneMap
from .pcb_rf_antenna_models import (
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
)
from .pcb_signal_path_rule_models import PcbSignalPathRuleMap
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)
from .pcb_thermal_via_models import PcbThermalViaCoverageReport, PcbThermalViaMap
from .pcb_touch_pad_clearance_models import (
    PcbTouchPadClearanceCoverageReport,
    PcbTouchPadClearanceMap,
    PcbTouchPadClearanceRequestSet,
)
from .pcb_track_width_models import (
    PcbTrackWidthCoverageReport,
    PcbTrackWidthMap,
)
from .project_models import ProjectKind


def scan_pcb_geometry(
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    policy: DesignLintPolicy,
    native_summary: Path,
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
    tuple[Candidate, ...],
]:
    """Capture one native PCB snapshot for all configured geometry review maps."""
    decoupling_map: PcbDecouplingMap | None = policy.pcb_decoupling_map
    protection_path_map: PcbProtectionPathMap | None = policy.pcb_protection_path_map
    track_width_map: PcbTrackWidthMap | None = policy.pcb_track_width_map
    reference_plane_map: PcbReferencePlaneMap | None = policy.pcb_reference_plane_map
    switching_loop_map: PcbSwitchingLoopMap | None = policy.pcb_switching_loop_map
    signal_path_map: PcbSignalPathRuleMap | None = policy.pcb_signal_path_rule_map
    keepout_map: PcbKeepoutMap | None = policy.pcb_keepout_map
    rf_antenna_map: PcbRfModuleAntennaMap | None = policy.pcb_rf_module_antenna_map
    touch_pad_clearance_map: PcbTouchPadClearanceMap | None = policy.pcb_touch_pad_clearance_map
    thermal_via_map: PcbThermalViaMap | None = policy.pcb_thermal_via_map
    fiducial_map: PcbFiducialMap | None = policy.pcb_fiducial_map
    scan_modes = resolve_pcb_geometry_scan_modes(config, policy)
    inventory_mode = scan_modes.inventory_modes.inventory
    if (
        decoupling_map is None
        and protection_path_map is None
        and track_width_map is None
        and reference_plane_map is None
        and switching_loop_map is None
        and signal_path_map is None
        and keepout_map is None
        and rf_antenna_map is None
        and touch_pad_clearance_map is None
        and thermal_via_map is None
        and fiducial_map is None
        and not track_angle_geometry_scan_required(config, policy)
        and not scan_modes.inventory_required
    ):
        return (
            *pcb_geometry_fast_path_reports(
                config, policy, inventory_mode=inventory_mode, mode="not_requested"
            ),
            track_angle_geometry_candidates_for_scan(config, policy, coach.source_hashes),
        )
    if (
        all(scan_modes.disabled.values())
        and not track_angle_geometry_scan_required(config, policy)
        and not scan_modes.route_measurement_active
    ):
        return (
            *pcb_geometry_fast_path_reports(
                config, policy, inventory_mode=inventory_mode, mode="disabled"
            ),
            track_angle_geometry_candidates_for_scan(config, policy, coach.source_hashes),
        )
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    output = root / "build" / "design-lint" / f"pcb-geometry-{uuid4().hex[:12]}"
    board_hash: str | None = None
    inventory_report = PcbComponentInventoryCoverageReport(
        status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
        mode=inventory_mode if config.kind is ProjectKind.PCB else None,
    )
    modes = scan_modes.rules
    try:
        netlist_sha256 = coach.netlist_sha256
        if netlist_sha256 is None:
            raise ValueError("Source-bound native netlist hash is unavailable")
        touch_requests = (
            PcbTouchPadClearanceRequestSet(requests=touch_pad_clearance_map.requirements)
            if touch_pad_clearance_map is not None
            and not scan_modes.disabled["touch_pad_clearance"]
            else None
        )
        evidence = capture_pcb_geometry_source(
            root,
            config,
            coach,
            output,
            touch_pad_clearance_requests=touch_requests,
        )
        board_hash = evidence.board_sha256
        if scan_modes.inventory_required:
            inventory_report = scan_pcb_component_inventory(
                root,
                config,
                coach,
                evidence,
                output,
                inventory_mode=scan_modes.inventory_modes.scan_mode,
                population_mode=scan_modes.inventory_modes.population,
                value_mode=scan_modes.inventory_modes.value,
                pad_net_mode=scan_modes.inventory_modes.pad_net,
                board_only_mode=scan_modes.inventory_modes.board_only,
                required_fitted_reference_map=policy.pcb_required_fitted_reference_map,
                required_fitted_reference_mode=(
                    scan_modes.inventory_modes.required_fitted_reference
                ),
            )
        fiducial_coverage = (
            evaluate_pcb_fiducials(
                fiducial_map,
                scan_modes.rules["pcb.fiducial_count"],
                evidence,
                netlist_sha256,
            )
            if fiducial_map is not None and not scan_modes.disabled["fiducial"]
            else blocked_pcb_fiducial_coverage(
                fiducial_map,
                scan_modes.rules["pcb.fiducial_count"],
                board_relative,
                "Fiducial coverage is disabled by project policy",
            )
        )
        inventory_report = inventory_report.model_copy(
            update={"fiducial_coverage": fiducial_coverage}
        )
        (
            decoupling_report,
            protection_path_report,
            track_width_report,
            reference_plane_report,
            switching_loop_report,
            thermal_via_report,
        ) = measurement_coverage_reports(
            decoupling_map=decoupling_map,
            protection_path_map=protection_path_map,
            track_width_map=track_width_map,
            reference_plane_map=reference_plane_map,
            switching_loop_map=switching_loop_map,
            thermal_via_map=thermal_via_map,
            modes=modes,
            evidence=evidence,
            netlist_sha256=netlist_sha256,
        )
        (
            signal_path_report,
            keepout_report,
            rf_antenna_report,
            touch_pad_clearance_report,
        ) = layout_coverage_reports(
            root=root,
            config=config,
            coach=coach,
            native_summary=native_summary,
            signal_path_map=signal_path_map,
            keepout_map=keepout_map,
            rf_antenna_map=rf_antenna_map,
            touch_pad_clearance_map=touch_pad_clearance_map,
            modes=modes,
            evidence=evidence,
        )
        signal_path_report = measure_route_skew_for_geometry_scan(
            signal_path_report,
            policy=policy,
            coach=coach,
            evidence=evidence,
            netlist_sha256=netlist_sha256,
        )
        verify_pcb_geometry_receipts(
            evidence.snapshot,
            evidence.snapshot_path,
            evidence.snapshot_sha256,
            evidence.command,
            evidence.command_path,
            evidence.command_sha256,
        )
        return (
            decoupling_report,
            protection_path_report,
            track_width_report,
            reference_plane_report,
            switching_loop_report,
            signal_path_report,
            keepout_report,
            rf_antenna_report,
            touch_pad_clearance_report,
            inventory_report,
            thermal_via_report,
            track_angle_geometry_candidates_for_scan(
                config,
                policy,
                coach.source_hashes,
                evidence=evidence,
                netlist_sha256=netlist_sha256,
            ),
        )
    except (OSError, ValueError, TypeError) as exc:
        issue = f"Could not bind native PCB geometry evidence: {exc}"
        decoupling_report = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.decoupling_proximity"],
                map_sha256=map_sha256(decoupling_map),
                board_path=board_relative,
                issue=issue,
            )
            if decoupling_map is not None and not scan_modes.disabled["decoupling"]
            else PcbDecouplingCoverageReport(
                status="DISABLED", mode=modes["pcb.decoupling_proximity"]
            )
            if decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
        protection_path_report = (
            PcbProtectionPathCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.protection_entry_path"],
                map_sha256=map_sha256(protection_path_map),
                board_path=board_relative,
                issue=issue,
            )
            if protection_path_map is not None and not scan_modes.disabled["protection_path"]
            else PcbProtectionPathCoverageReport(
                status="DISABLED", mode=modes["pcb.protection_entry_path"]
            )
            if protection_path_map is not None
            else PcbProtectionPathCoverageReport()
        )
        track_width_report = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.minimum_track_width"],
                map_sha256=map_sha256(track_width_map),
                board_path=board_relative,
                issue=issue,
            )
            if track_width_map is not None and not scan_modes.disabled["track_width"]
            else PcbTrackWidthCoverageReport(
                status="DISABLED", mode=modes["pcb.minimum_track_width"]
            )
            if track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
        reference_plane_report = (
            PcbReferencePlaneCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.reference_plane_coverage"],
                map_sha256=map_sha256(reference_plane_map),
                board_path=board_relative,
                issue=issue,
            )
            if reference_plane_map is not None and not scan_modes.disabled["reference_plane"]
            else PcbReferencePlaneCoverageReport(
                status="DISABLED", mode=modes["pcb.reference_plane_coverage"]
            )
            if reference_plane_map is not None
            else PcbReferencePlaneCoverageReport()
        )
        switching_loop_report = (
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.switching_loop_geometry"],
                map_sha256=map_sha256(switching_loop_map),
                board_path=board_relative,
                issue=issue,
            )
            if switching_loop_map is not None and not scan_modes.disabled["switching_loop"]
            else PcbSwitchingLoopCoverageReport(
                status="DISABLED", mode=modes["pcb.switching_loop_geometry"]
            )
            if switching_loop_map is not None
            else PcbSwitchingLoopCoverageReport()
        )
        signal_path_report = (
            PcbSignalPathRuleCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.signal_path_rule_coverage"],
                map_sha256=map_sha256(signal_path_map),
                issue=issue,
            )
            if signal_path_map is not None and not scan_modes.disabled["signal_path"]
            else PcbSignalPathRuleCoverageReport(
                status="DISABLED", mode=modes["pcb.signal_path_rule_coverage"]
            )
            if signal_path_map is not None
            else PcbSignalPathRuleCoverageReport()
        )
        keepout_report = (
            PcbKeepoutCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.keepout_intent_coverage"],
                map_sha256=map_sha256(keepout_map),
                board_path=board_relative,
                issue=issue,
            )
            if keepout_map is not None and not scan_modes.disabled["keepout"]
            else PcbKeepoutCoverageReport(
                status="DISABLED", mode=modes["pcb.keepout_intent_coverage"]
            )
            if keepout_map is not None
            else PcbKeepoutCoverageReport()
        )
        rf_antenna_report = (
            PcbRfModuleAntennaCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.rf_module_antenna_keepout_coverage"],
                map_sha256=map_sha256(rf_antenna_map),
                board_path=board_relative,
                issue=issue,
            )
            if rf_antenna_map is not None and not scan_modes.disabled["rf_antenna"]
            else PcbRfModuleAntennaCoverageReport(
                status="DISABLED", mode=modes["pcb.rf_module_antenna_keepout_coverage"]
            )
            if rf_antenna_map is not None
            else PcbRfModuleAntennaCoverageReport()
        )
        touch_pad_clearance_report = (
            PcbTouchPadClearanceCoverageReport(
                status="BLOCKED",
                mode=modes["pcb.touch_pad_reference_clearance"],
                map_sha256=map_sha256(touch_pad_clearance_map),
                board_path=board_relative,
                issue=issue,
            )
            if touch_pad_clearance_map is not None
            and not scan_modes.disabled["touch_pad_clearance"]
            else PcbTouchPadClearanceCoverageReport(
                status="DISABLED", mode=modes["pcb.touch_pad_reference_clearance"]
            )
            if touch_pad_clearance_map is not None
            else PcbTouchPadClearanceCoverageReport()
        )
        thermal_via_report = blocked_thermal_via_coverage(
            thermal_via_map, modes["pcb.thermal_via_coverage"], board_relative, issue
        )
        inventory_report = (
            PcbComponentInventoryCoverageReport(
                status="BLOCKED",
                mode=scan_modes.inventory_modes.scan_mode,
                netlist_sha256=coach.netlist_sha256,
                board_path=board_relative,
                board_sha256=board_hash,
                pad_net_comparison_status=(
                    "BLOCKED" if scan_modes.inventory_modes.pad_net != "off" else "NOT_APPLICABLE"
                ),
                pad_net_comparison_issue=(
                    issue if scan_modes.inventory_modes.pad_net != "off" else None
                ),
                board_only_footprint_coverage=(
                    PcbBoardOnlyFootprintCoverage(
                        status="BLOCKED",
                        mode=scan_modes.inventory_modes.board_only,
                        issue=issue,
                    )
                    if scan_modes.inventory_modes.board_only != "off"
                    else PcbBoardOnlyFootprintCoverage()
                ),
                issue=issue,
            )
            if scan_modes.inventory_required
            else PcbComponentInventoryCoverageReport(
                status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
                mode=inventory_mode if config.kind is ProjectKind.PCB else None,
            )
        )
        inventory_report = inventory_report.model_copy(
            update={
                "fiducial_coverage": blocked_pcb_fiducial_coverage(
                    fiducial_map,
                    modes["pcb.fiducial_count"],
                    board_relative,
                    issue,
                )
            }
        )
    return (
        decoupling_report,
        protection_path_report,
        track_width_report,
        reference_plane_report,
        switching_loop_report,
        signal_path_report,
        keepout_report,
        rf_antenna_report,
        touch_pad_clearance_report,
        inventory_report,
        thermal_via_report,
        track_angle_geometry_candidates_for_scan(
            config,
            policy,
            coach.source_hashes,
            issue=issue,
        ),
    )
