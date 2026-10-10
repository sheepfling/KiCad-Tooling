"""Coverage adapters for measured PCB placement, width, plane, and route checks."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from .design_lint_pcb_coverage_common import (
    CoverageEntry,
    PcbGeometrySourceEvidence,
    PcbRuleMode,
    geometry_coverage_report,
)
from .models import (
    Digest,
    PcbDecouplingMap,
    PcbProtectionPathCoverageReport,
    PcbProtectionPathMap,
)
from .pcb_connectivity_snapshot import PcbConnectivitySnapshot
from .pcb_decoupling import pcb_decoupling_entries
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_protection_path import pcb_protection_path_entries
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport, PcbReferencePlaneMap
from .pcb_reference_planes import pcb_reference_plane_entries
from .pcb_switching_loop_models import (
    PcbSwitchingLoopCoverageReport,
    PcbSwitchingLoopMap,
)
from .pcb_switching_loop_review import pcb_switching_loop_entries
from .pcb_track_width import pcb_track_width_entries
from .pcb_track_width_models import PcbTrackWidthCoverageReport, PcbTrackWidthMap

MapT = TypeVar("MapT", bound=BaseModel)
ReportT = TypeVar("ReportT", bound=BaseModel)


def _coverage(
    report_type: type[ReportT],
    requirements: MapT | None,
    mode: PcbRuleMode,
    entry_scanner: Callable[[MapT, PcbConnectivitySnapshot], tuple[CoverageEntry, ...]],
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: Digest,
) -> ReportT:
    if requirements is None:
        return report_type()
    if mode == "off":
        return report_type(status="DISABLED", mode=mode)
    entries = entry_scanner(requirements, evidence.snapshot)
    return geometry_coverage_report(
        report_type, requirements, mode, entries, evidence, netlist_sha256
    )


def measurement_coverage_reports(
    *,
    decoupling_map: PcbDecouplingMap | None,
    protection_path_map: PcbProtectionPathMap | None,
    track_width_map: PcbTrackWidthMap | None,
    reference_plane_map: PcbReferencePlaneMap | None,
    switching_loop_map: PcbSwitchingLoopMap | None,
    modes: dict[str, PcbRuleMode],
    evidence: PcbGeometrySourceEvidence,
    netlist_sha256: Digest,
) -> tuple[
    PcbDecouplingCoverageReport,
    PcbProtectionPathCoverageReport,
    PcbTrackWidthCoverageReport,
    PcbReferencePlaneCoverageReport,
    PcbSwitchingLoopCoverageReport,
]:
    """Build coverage for the measured PCB geometry requirement maps."""
    return (
        _coverage(
            PcbDecouplingCoverageReport,
            decoupling_map,
            modes["pcb.decoupling_proximity"],
            pcb_decoupling_entries,
            evidence,
            netlist_sha256,
        ),
        _coverage(
            PcbProtectionPathCoverageReport,
            protection_path_map,
            modes["pcb.protection_entry_path"],
            pcb_protection_path_entries,
            evidence,
            netlist_sha256,
        ),
        _coverage(
            PcbTrackWidthCoverageReport,
            track_width_map,
            modes["pcb.minimum_track_width"],
            pcb_track_width_entries,
            evidence,
            netlist_sha256,
        ),
        _coverage(
            PcbReferencePlaneCoverageReport,
            reference_plane_map,
            modes["pcb.reference_plane_coverage"],
            pcb_reference_plane_entries,
            evidence,
            netlist_sha256,
        ),
        _coverage(
            PcbSwitchingLoopCoverageReport,
            switching_loop_map,
            modes["pcb.switching_loop_geometry"],
            pcb_switching_loop_entries,
            evidence,
            netlist_sha256,
        ),
    )
