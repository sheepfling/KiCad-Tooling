"""Cross-check PCB evidence sources embedded in one design-lint report."""

from __future__ import annotations

from typing import TypeAlias

from .model_primitives import Digest
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport
from .pcb_decoupling_models import PcbDecouplingCoverageReport
from .pcb_drc_models import PcbDifferentialPairRuleCoverageReport, PcbSignalPathRuleCoverageReport
from .pcb_keepout_models import PcbKeepoutCoverageReport
from .pcb_protection_path_models import PcbProtectionPathCoverageReport
from .pcb_reference_plane_models import PcbReferencePlaneCoverageReport
from .pcb_rf_antenna_models import PcbRfModuleAntennaCoverageReport
from .pcb_switching_loop_models import PcbSwitchingLoopCoverageReport
from .pcb_touch_pad_clearance_models import PcbTouchPadClearanceCoverageReport
from .pcb_track_width_models import PcbTrackWidthCoverageReport

PcbSourceCoverage: TypeAlias = (
    PcbComponentInventoryCoverageReport
    | PcbDecouplingCoverageReport
    | PcbDifferentialPairRuleCoverageReport
    | PcbKeepoutCoverageReport
    | PcbProtectionPathCoverageReport
    | PcbReferencePlaneCoverageReport
    | PcbRfModuleAntennaCoverageReport
    | PcbSignalPathRuleCoverageReport
    | PcbSwitchingLoopCoverageReport
    | PcbTouchPadClearanceCoverageReport
    | PcbTrackWidthCoverageReport
)

PcbNetlistSourceCoverage: TypeAlias = (
    PcbComponentInventoryCoverageReport
    | PcbDecouplingCoverageReport
    | PcbKeepoutCoverageReport
    | PcbProtectionPathCoverageReport
    | PcbReferencePlaneCoverageReport
    | PcbRfModuleAntennaCoverageReport
    | PcbSwitchingLoopCoverageReport
    | PcbTouchPadClearanceCoverageReport
    | PcbTrackWidthCoverageReport
)


def validate_pcb_source_consistency(
    reports: tuple[PcbSourceCoverage, ...],
    *,
    report_netlist_sha256: Digest | None,
    netlist_reports: tuple[PcbNetlistSourceCoverage, ...],
) -> None:
    """Reject one report that combines observations from different boards or toolchains."""
    _require_one_value(
        "board SHA-256",
        tuple(item.board_sha256 for item in reports),
    )
    _require_one_value(
        "KiCad version",
        tuple(item.kicad_version for item in reports),
    )
    _require_one_value("native image", tuple(item.image for item in reports))
    for name, item in zip(
        (
            "PCB component inventory",
            "PCB decoupling",
            "PCB keepout",
            "PCB protection-path",
            "PCB reference-plane",
            "PCB RF antenna",
            "PCB switching-loop",
            "PCB touch-clearance",
            "PCB track-width",
        ),
        netlist_reports,
        strict=True,
    ):
        required_statuses = (
            frozenset({"COMPLETE"})
            if name == "PCB component inventory"
            else frozenset({"COMPLETE", "INCOMPLETE"})
        )
        if item.netlist_sha256 is None and item.status not in required_statuses:
            continue
        if report_netlist_sha256 is None or item.netlist_sha256 != report_netlist_sha256:
            raise ValueError(f"{name} coverage must use this report's native netlist")


def _require_one_value(name: str, values: tuple[str | None, ...]) -> None:
    observed = {value for value in values if value is not None}
    if len(observed) > 1:
        raise ValueError(f"PCB coverage reports must use one {name}")
