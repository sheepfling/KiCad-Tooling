"""Coverage adapters for PCB path rules, keepout intent, and RF antenna maps."""

from __future__ import annotations

from pathlib import Path

from .design_lint_pcb_coverage_common import (
    PcbGeometrySourceEvidence,
    PcbRuleMode,
    geometry_coverage_report,
    map_sha256,
)
from .discovery import ProjectConfig
from .models import (
    ContractCoachReport,
    Digest,
    PcbKeepoutCoverageReport,
    PcbKeepoutMap,
)
from .pcb_drc_models import (
    PcbSignalPathRuleCoverageReport,
    PcbSignalPathRuleMap,
)
from .pcb_drc_source_scan import scan_source_bound_signal_path_map
from .pcb_keepouts import pcb_keepout_entries
from .pcb_rf_antenna import pcb_rf_module_antenna_entries
from .pcb_rf_antenna_models import (
    PcbRfModuleAntennaCoverageReport,
    PcbRfModuleAntennaMap,
)


def layout_coverage_reports(
    *,
    root: Path,
    config: ProjectConfig,
    coach: ContractCoachReport,
    native_summary: Path,
    signal_path_map: PcbSignalPathRuleMap | None,
    keepout_map: PcbKeepoutMap | None,
    rf_antenna_map: PcbRfModuleAntennaMap | None,
    modes: dict[str, PcbRuleMode],
    evidence: PcbGeometrySourceEvidence,
) -> tuple[
    PcbSignalPathRuleCoverageReport,
    PcbKeepoutCoverageReport,
    PcbRfModuleAntennaCoverageReport,
]:
    """Build layout and RF coverage from the already verified native snapshot."""
    if coach.netlist_sha256 is None:
        raise ValueError("Source-bound native netlist hash is unavailable for PCB coverage")
    netlist_sha256: Digest = coach.netlist_sha256
    signal_path_mode = modes["pcb.signal_path_rule_coverage"]
    signal_path_report = PcbSignalPathRuleCoverageReport()
    if signal_path_map is not None:
        if signal_path_mode == "off":
            signal_path_report = PcbSignalPathRuleCoverageReport(
                status="DISABLED", mode=signal_path_mode, map_sha256=map_sha256(signal_path_map)
            )
        else:
            if coach.observed is None:
                raise ValueError("Source-bound native netlist is unavailable for mapped paths")
            pcb_command_path = evidence.command_path
            signal_path_report = scan_source_bound_signal_path_map(
                root,
                config,
                signal_path_map,
                coach.observed,
                dict(coach.source_hashes),
                native_summary,
                evidence.snapshot,
                evidence.snapshot_path,
                evidence.snapshot_sha256,
                evidence.command,
                pcb_command_path,
                evidence.command_sha256,
                signal_path_mode,
            )

    keepout_mode = modes["pcb.keepout_intent_coverage"]
    keepout_report = PcbKeepoutCoverageReport()
    if keepout_map is not None:
        if keepout_mode == "off":
            keepout_report = PcbKeepoutCoverageReport(
                status="DISABLED", mode=keepout_mode, map_sha256=map_sha256(keepout_map)
            )
        else:
            entries = pcb_keepout_entries(keepout_map, evidence.snapshot)
            keepout_report = geometry_coverage_report(
                PcbKeepoutCoverageReport,
                keepout_map,
                keepout_mode,
                entries,
                evidence,
                netlist_sha256,
            )

    rf_mode = modes["pcb.rf_module_antenna_keepout_coverage"]
    rf_antenna_report = PcbRfModuleAntennaCoverageReport()
    if rf_antenna_map is not None:
        if rf_mode == "off":
            rf_antenna_report = PcbRfModuleAntennaCoverageReport(
                status="DISABLED", mode=rf_mode, map_sha256=map_sha256(rf_antenna_map)
            )
        else:
            if coach.observed is None:
                raise ValueError("Source-bound native netlist is unavailable for mapped RF modules")
            entries = pcb_rf_module_antenna_entries(
                rf_antenna_map, coach.observed, evidence.snapshot
            )
            rf_antenna_report = geometry_coverage_report(
                PcbRfModuleAntennaCoverageReport,
                rf_antenna_map,
                rf_mode,
                entries,
                evidence,
                netlist_sha256,
            )
    return signal_path_report, keepout_report, rf_antenna_report
