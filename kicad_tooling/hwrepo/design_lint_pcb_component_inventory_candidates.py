"""PCB component inventory finding translation for design-lint reports."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def pcb_component_inventory_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate source-bound inventory gaps and missing placements into findings."""
    if report is None or report.status in {"NOT_APPLICABLE", "DISABLED"}:
        return ()
    if report.status == "BLOCKED":
        return (
            Candidate(
                rule_id="pcb.schematic_component_inventory",
                subject="native PCB footprint inventory unavailable",
                message=(
                    "The source-bound PCB footprint inventory could not be compared with the "
                    "native schematic netlist. No placement conclusion is available."
                ),
                evidence={
                    "coverage_issue": (report.issue or "unavailable",),
                    "netlist_sha256": (
                        () if report.netlist_sha256 is None else (report.netlist_sha256,)
                    ),
                    "board_path": (() if report.board_path is None else (report.board_path,)),
                    "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
                },
            ),
        )
    return tuple(
        Candidate(
            rule_id="pcb.schematic_component_inventory",
            subject=f"{item.reference}: schematic footprint absent from PCB",
            message=(
                "This fitted schematic component has an assigned footprint, but the source-bound "
                "native PCB snapshot has no footprint with the same reference. Confirm whether "
                "the component is intentionally off-board; otherwise restore its board placement. "
                "This check does not infer electrical role, assembly intent, or manufacturability."
            ),
            evidence={
                "reference": (item.reference,),
                "assigned_footprint": (item.assigned_footprint,),
                "netlist_sha256": (report.netlist_sha256 or "unavailable",),
                "board_path": (report.board_path or "unavailable",),
                "board_sha256": (report.board_sha256 or "unavailable",),
                "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
                "snapshot_schema": (report.snapshot_schema or "unavailable",),
                "kicad_version": (report.kicad_version or "unavailable",),
                "image": (report.image or "unavailable",),
                "probe_sha256": (report.probe_sha256 or "unavailable",),
            },
        )
        for item in report.missing_placements
    )
