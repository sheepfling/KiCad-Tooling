"""Source-bound native PCB geometry scan orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from ..validate import hashes
from .contract_coach import pinned_image
from .contracts import repo_path, write_model
from .design_lint_pcb_coverage_common import PcbGeometrySourceEvidence, PcbRuleMode
from .design_lint_pcb_layout_coverage import layout_coverage_reports
from .design_lint_pcb_measurement_coverage import measurement_coverage_reports
from .discovery import ProjectConfig
from .evidence import digest
from .models import (
    ContractCoachReport,
    DesignLintPolicy,
    PcbDecouplingMap,
    PcbKeepoutCoverageReport,
    PcbKeepoutMap,
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
    ProjectKind,
)
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import (
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport, PcbReferencePlaneMap
from .pcb_return_path_capture import (
    capture_native_pcb_connectivity,
    expected_probe_sha256,
    native_pcb_command_matches,
)
from .pcb_rf_antenna_models import (
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
)
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)
from .pcb_track_width_models import (
    PcbTrackWidthCoverageReport,
    PcbTrackWidthMap,
)


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
    if (
        decoupling_map is None
        and protection_path_map is None
        and track_width_map is None
        and reference_plane_map is None
        and switching_loop_map is None
        and signal_path_map is None
        and keepout_map is None
        and rf_antenna_map is None
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
        )
    overrides = {item.rule_id: item for item in policy.rules}
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
    if (
        decoupling_disabled
        and protection_path_disabled
        and track_width_disabled
        and reference_plane_disabled
        and switching_loop_disabled
        and signal_path_disabled
        and keepout_disabled
        and rf_antenna_disabled
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
        )
    board_relative = Path(config.project).with_suffix(".kicad_pcb").as_posix()
    board_path = repo_path(root, board_relative)
    output = root / "build" / "design-lint" / f"pcb-geometry-{uuid4().hex[:12]}"
    board_hash: str | None = None
    try:
        if config.kind is not ProjectKind.PCB:
            raise ValueError("PCB geometry requirements need an authoritative PCB project")
        if coach.netlist_sha256 is None:
            raise ValueError("Source-bound native netlist hash is unavailable")
        board_hash = digest(board_path)
        if coach.source_hashes.get(board_relative) != board_hash:
            raise ValueError(
                "Authoritative PCB is absent from, or differs from, native source hashes"
            )
        command, snapshot = capture_native_pcb_connectivity(root, config, output)
        if snapshot is None:
            raise ValueError(
                "Native PCB geometry probe failed; inspect "
                f"{output.relative_to(root).as_posix()}/native.command.json"
            )
        if (
            snapshot.schema_version not in {"10", "11", "12"}
            or snapshot.board_sha256 != board_hash
            or snapshot.kicad_version != config.kicad_version
            or snapshot.image != pinned_image(config.image)
            or snapshot.probe_sha256 != expected_probe_sha256()
            or not snapshot.zones_refilled
            or not native_pcb_command_matches(command, config)
        ):
            raise ValueError(
                "Native PCB geometry evidence does not match the reviewed source/toolchain"
            )
        snapshot_path = output / "snapshot.json"
        write_model(snapshot_path, snapshot)
        if (
            digest(board_path) != board_hash
            or hashes(root, config.source_roots) != coach.source_hashes
        ):
            raise ValueError("Project sources changed during native PCB geometry capture")
        snapshot_relative = snapshot_path.relative_to(root).as_posix()
        snapshot_hash = digest(snapshot_path)
        probe_hash = expected_probe_sha256()
        pcb_command_path = output / "native.command.json"
        evidence = PcbGeometrySourceEvidence(
            board_path=board_relative,
            board_sha256=board_hash,
            snapshot_relative_path=snapshot_relative,
            snapshot_path=snapshot_path,
            snapshot_sha256=snapshot_hash,
            probe_sha256=probe_hash,
            snapshot=snapshot,
            command=command,
            command_path=pcb_command_path,
            command_sha256=digest(pcb_command_path),
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
            netlist_sha256=coach.netlist_sha256,
        )
        signal_path_report, keepout_report, rf_antenna_report = layout_coverage_reports(
            root=root,
            config=config,
            coach=coach,
            native_summary=native_summary,
            signal_path_map=signal_path_map,
            keepout_map=keepout_map,
            rf_antenna_map=rf_antenna_map,
            modes=modes,
            evidence=evidence,
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
        )
    except (OSError, ValueError, TypeError) as exc:
        issue = f"Could not bind native PCB geometry evidence: {exc}"
        decoupling_report = (
            PcbDecouplingCoverageReport(
                status="BLOCKED",
                mode=decoupling_mode,
                map_sha256=hashlib.sha256(
                    decoupling_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    protection_path_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    track_width_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    reference_plane_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    switching_loop_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    signal_path_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    keepout_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
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
                map_sha256=hashlib.sha256(
                    rf_antenna_map.model_dump_json().encode("utf-8")
                ).hexdigest(),
                board_path=board_relative,
                issue=issue,
            )
            if rf_antenna_map is not None and not rf_antenna_disabled
            else PcbRfModuleAntennaCoverageReport(status="DISABLED", mode=rf_antenna_mode)
            if rf_antenna_map is not None
            else PcbRfModuleAntennaCoverageReport()
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
    )
