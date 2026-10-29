"""Source-bound native PCB geometry scan orchestration."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .design_lint_pcb_component_inventory_scan import (
    resolve_pcb_component_inventory_modes,
    scan_pcb_component_inventory,
)
from .design_lint_pcb_coverage_common import (
    PcbRuleMode,
    map_sha256,
)
from .design_lint_pcb_geometry_capture import capture_pcb_geometry_source
from .design_lint_pcb_layout_coverage import layout_coverage_reports
from .design_lint_pcb_measurement_coverage import measurement_coverage_reports
from .design_lint_policy_models import DesignLintPolicy
from .discovery import ProjectConfig
from .models import ContractCoachReport
from .pcb_board_only_footprint_models import PcbBoardOnlyFootprintCoverage
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport, PcbDecouplingMap
from .pcb_drc_models import (
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
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
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)
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
    inventory_modes = resolve_pcb_component_inventory_modes(policy)
    inventory_mode = inventory_modes.inventory
    population_mode = inventory_modes.population
    value_mode = inventory_modes.value
    pad_net_mode = inventory_modes.pad_net
    board_only_mode = inventory_modes.board_only
    required_fitted_reference_mode = inventory_modes.required_fitted_reference
    inventory_required = config.kind is ProjectKind.PCB and inventory_modes.required
    overrides = {item.rule_id: item for item in policy.rules}
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
        and not inventory_required
    ):
        return (
            PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(),
            PcbSignalPathRuleCoverageReport(),
            PcbKeepoutCoverageReport(),
            PcbRfModuleAntennaCoverageReport(),
            PcbTouchPadClearanceCoverageReport(),
            PcbComponentInventoryCoverageReport(
                status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
                mode=inventory_mode if config.kind is ProjectKind.PCB else None,
            ),
        )
    decoupling_override = overrides.get("pcb.decoupling_proximity")
    decoupling_mode = "review" if decoupling_override is None else decoupling_override.mode
    protection_path_override = overrides.get("pcb.protection_entry_path")
    protection_path_mode = (
        "review" if protection_path_override is None else protection_path_override.mode
    )
    track_width_override = overrides.get("pcb.minimum_track_width")
    track_width_mode = "review" if track_width_override is None else track_width_override.mode
    switching_loop_override = overrides.get("pcb.switching_loop_geometry")
    switching_loop_mode = (
        "review" if switching_loop_override is None else switching_loop_override.mode
    )
    signal_path_override = overrides.get("pcb.signal_path_rule_coverage")
    signal_path_mode = "review" if signal_path_override is None else signal_path_override.mode
    keepout_override = overrides.get("pcb.keepout_intent_coverage")
    keepout_mode = "review" if keepout_override is None else keepout_override.mode
    rf_antenna_override = overrides.get("pcb.rf_module_antenna_keepout_coverage")
    rf_antenna_mode = "review" if rf_antenna_override is None else rf_antenna_override.mode
    touch_pad_clearance_override = overrides.get("pcb.touch_pad_reference_clearance")
    touch_pad_clearance_mode = (
        "review" if touch_pad_clearance_override is None else touch_pad_clearance_override.mode
    )
    reference_plane_override = overrides.get("pcb.reference_plane_coverage")
    reference_plane_mode = (
        "review" if reference_plane_override is None else reference_plane_override.mode
    )
    decoupling_disabled = decoupling_map is None or decoupling_mode == "off"
    protection_path_disabled = protection_path_map is None or protection_path_mode == "off"
    track_width_disabled = track_width_map is None or track_width_mode == "off"
    reference_plane_disabled = reference_plane_map is None or reference_plane_mode == "off"
    switching_loop_disabled = switching_loop_map is None or switching_loop_mode == "off"
    signal_path_disabled = signal_path_map is None or signal_path_mode == "off"
    keepout_disabled = keepout_map is None or keepout_mode == "off"
    rf_antenna_disabled = rf_antenna_map is None or rf_antenna_mode == "off"
    touch_pad_clearance_disabled = (
        touch_pad_clearance_map is None or touch_pad_clearance_mode == "off"
    )
    inventory_disabled = not inventory_required
    if (
        decoupling_disabled
        and protection_path_disabled
        and track_width_disabled
        and reference_plane_disabled
        and switching_loop_disabled
        and signal_path_disabled
        and keepout_disabled
        and rf_antenna_disabled
        and touch_pad_clearance_disabled
        and inventory_disabled
    ):
        return (
            PcbDecouplingCoverageReport(status="DISABLED", mode=decoupling_mode)
            if decoupling_map is not None
            else PcbDecouplingCoverageReport(),
            PcbProtectionPathCoverageReport(status="DISABLED", mode=protection_path_mode)
            if protection_path_map is not None
            else PcbProtectionPathCoverageReport(),
            PcbTrackWidthCoverageReport(status="DISABLED", mode=track_width_mode)
            if track_width_map is not None
            else PcbTrackWidthCoverageReport(),
            PcbReferencePlaneCoverageReport(status="DISABLED", mode=reference_plane_mode)
            if reference_plane_map is not None
            else PcbReferencePlaneCoverageReport(),
            PcbSwitchingLoopCoverageReport(status="DISABLED", mode=switching_loop_mode)
            if switching_loop_map is not None
            else PcbSwitchingLoopCoverageReport(),
            PcbSignalPathRuleCoverageReport(status="DISABLED", mode=signal_path_mode)
            if signal_path_map is not None
            else PcbSignalPathRuleCoverageReport(),
            PcbKeepoutCoverageReport(status="DISABLED", mode=keepout_mode)
            if keepout_map is not None
            else PcbKeepoutCoverageReport(),
            PcbRfModuleAntennaCoverageReport(status="DISABLED", mode=rf_antenna_mode)
            if rf_antenna_map is not None
            else PcbRfModuleAntennaCoverageReport(),
            PcbTouchPadClearanceCoverageReport(status="DISABLED", mode=touch_pad_clearance_mode)
            if touch_pad_clearance_map is not None
            else PcbTouchPadClearanceCoverageReport(),
            PcbComponentInventoryCoverageReport(
                status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
                mode=inventory_mode if config.kind is ProjectKind.PCB else None,
            ),
        )
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    output = root / "build" / "design-lint" / f"pcb-geometry-{uuid4().hex[:12]}"
    board_hash: str | None = None
    inventory_report = PcbComponentInventoryCoverageReport(
        status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
        mode=inventory_mode if config.kind is ProjectKind.PCB else None,
    )
    try:
        netlist_sha256 = coach.netlist_sha256
        if netlist_sha256 is None:
            raise ValueError("Source-bound native netlist hash is unavailable")
        touch_requests = (
            PcbTouchPadClearanceRequestSet(requests=touch_pad_clearance_map.requirements)
            if touch_pad_clearance_map is not None and not touch_pad_clearance_disabled
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
        if inventory_required:
            inventory_report = scan_pcb_component_inventory(
                root,
                config,
                coach,
                evidence,
                output,
                inventory_mode=inventory_modes.scan_mode,
                population_mode=population_mode,
                value_mode=value_mode,
                pad_net_mode=pad_net_mode,
                board_only_mode=board_only_mode,
                required_fitted_reference_map=policy.pcb_required_fitted_reference_map,
                required_fitted_reference_mode=required_fitted_reference_mode,
            )
        modes: dict[str, PcbRuleMode] = {
            "pcb.decoupling_proximity": decoupling_mode,
            "pcb.protection_entry_path": protection_path_mode,
            "pcb.minimum_track_width": track_width_mode,
            "pcb.reference_plane_coverage": reference_plane_mode,
            "pcb.switching_loop_geometry": switching_loop_mode,
            "pcb.signal_path_rule_coverage": signal_path_mode,
            "pcb.keepout_intent_coverage": keepout_mode,
            "pcb.rf_module_antenna_keepout_coverage": rf_antenna_mode,
            "pcb.touch_pad_reference_clearance": touch_pad_clearance_mode,
            "pcb.schematic_component_inventory": inventory_mode,
            "pcb.schematic_pcb_dnp_mismatch": population_mode,
            "pcb.schematic_pcb_value_mismatch": value_mode,
            "pcb.schematic_pcb_pad_net_mismatch": pad_net_mode,
            "pcb.board_only_footprint": board_only_mode,
            "pcb.required_fitted_reference": required_fitted_reference_mode,
        }
        (
            decoupling_report,
            protection_path_report,
            track_width_report,
            reference_plane_report,
            switching_loop_report,
        ) = measurement_coverage_reports(
            decoupling_map=decoupling_map,
            protection_path_map=protection_path_map,
            track_width_map=track_width_map,
            reference_plane_map=reference_plane_map,
            switching_loop_map=switching_loop_map,
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
        )
    except (OSError, ValueError, TypeError) as exc:
        issue = f"Could not bind native PCB geometry evidence: {exc}"
        decoupling_report = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                mode=decoupling_mode,
                map_sha256=map_sha256(decoupling_map),
                board_path=board_relative,
                issue=issue,
            )
            if decoupling_map is not None and not decoupling_disabled
            else PcbDecouplingCoverageReport(status="DISABLED", mode=decoupling_mode)
            if decoupling_map is not None
            else PcbDecouplingCoverageReport()
        )
        protection_path_report = (
            PcbProtectionPathCoverageReport(
                status="BLOCKED",
                mode=protection_path_mode,
                map_sha256=map_sha256(protection_path_map),
                board_path=board_relative,
                issue=issue,
            )
            if protection_path_map is not None and not protection_path_disabled
            else PcbProtectionPathCoverageReport(status="DISABLED", mode=protection_path_mode)
            if protection_path_map is not None
            else PcbProtectionPathCoverageReport()
        )
        track_width_report = (
            PcbTrackWidthCoverageReport(
                status="BLOCKED",
                mode=track_width_mode,
                map_sha256=map_sha256(track_width_map),
                board_path=board_relative,
                issue=issue,
            )
            if track_width_map is not None and not track_width_disabled
            else PcbTrackWidthCoverageReport(status="DISABLED", mode=track_width_mode)
            if track_width_map is not None
            else PcbTrackWidthCoverageReport()
        )
        reference_plane_report = (
            PcbReferencePlaneCoverageReport(
                status="BLOCKED",
                mode=reference_plane_mode,
                map_sha256=map_sha256(reference_plane_map),
                board_path=board_relative,
                issue=issue,
            )
            if reference_plane_map is not None and not reference_plane_disabled
            else PcbReferencePlaneCoverageReport(status="DISABLED", mode=reference_plane_mode)
            if reference_plane_map is not None
            else PcbReferencePlaneCoverageReport()
        )
        switching_loop_report = (
            PcbSwitchingLoopCoverageReport(
                status="BLOCKED",
                mode=switching_loop_mode,
                map_sha256=map_sha256(switching_loop_map),
                board_path=board_relative,
                issue=issue,
            )
            if switching_loop_map is not None and not switching_loop_disabled
            else PcbSwitchingLoopCoverageReport(status="DISABLED", mode=switching_loop_mode)
            if switching_loop_map is not None
            else PcbSwitchingLoopCoverageReport()
        )
        signal_path_report = (
            PcbSignalPathRuleCoverageReport(
                status="BLOCKED",
                mode=signal_path_mode,
                map_sha256=map_sha256(signal_path_map),
                issue=issue,
            )
            if signal_path_map is not None and not signal_path_disabled
            else PcbSignalPathRuleCoverageReport(status="DISABLED", mode=signal_path_mode)
            if signal_path_map is not None
            else PcbSignalPathRuleCoverageReport()
        )
        keepout_report = (
            PcbKeepoutCoverageReport(
                status="BLOCKED",
                mode=keepout_mode,
                map_sha256=map_sha256(keepout_map),
                board_path=board_relative,
                issue=issue,
            )
            if keepout_map is not None and not keepout_disabled
            else PcbKeepoutCoverageReport(status="DISABLED", mode=keepout_mode)
            if keepout_map is not None
            else PcbKeepoutCoverageReport()
        )
        rf_antenna_report = (
            PcbRfModuleAntennaCoverageReport(
                status="BLOCKED",
                mode=rf_antenna_mode,
                map_sha256=map_sha256(rf_antenna_map),
                board_path=board_relative,
                issue=issue,
            )
            if rf_antenna_map is not None and not rf_antenna_disabled
            else PcbRfModuleAntennaCoverageReport(status="DISABLED", mode=rf_antenna_mode)
            if rf_antenna_map is not None
            else PcbRfModuleAntennaCoverageReport()
        )
        touch_pad_clearance_report = (
            PcbTouchPadClearanceCoverageReport(
                status="BLOCKED",
                mode=touch_pad_clearance_mode,
                map_sha256=map_sha256(touch_pad_clearance_map),
                board_path=board_relative,
                issue=issue,
            )
            if touch_pad_clearance_map is not None and not touch_pad_clearance_disabled
            else PcbTouchPadClearanceCoverageReport(
                status="DISABLED", mode=touch_pad_clearance_mode
            )
            if touch_pad_clearance_map is not None
            else PcbTouchPadClearanceCoverageReport()
        )
        inventory_report = (
            PcbComponentInventoryCoverageReport(
                status="BLOCKED",
                mode=inventory_modes.scan_mode,
                netlist_sha256=coach.netlist_sha256,
                board_path=board_relative,
                board_sha256=board_hash,
                pad_net_comparison_status=(
                    "BLOCKED" if pad_net_mode != "off" else "NOT_APPLICABLE"
                ),
                pad_net_comparison_issue=issue if pad_net_mode != "off" else None,
                board_only_footprint_coverage=(
                    PcbBoardOnlyFootprintCoverage(
                        status="BLOCKED",
                        mode=board_only_mode,
                        issue=issue,
                    )
                    if board_only_mode != "off"
                    else PcbBoardOnlyFootprintCoverage()
                ),
                issue=issue,
            )
            if inventory_required
            else PcbComponentInventoryCoverageReport(
                status="DISABLED" if config.kind is ProjectKind.PCB else "NOT_APPLICABLE",
                mode=inventory_mode if config.kind is ProjectKind.PCB else None,
            )
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
    )
