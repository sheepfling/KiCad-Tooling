"""Review prompts for PCB footprint references absent from the schematic."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport


def pcb_board_only_footprint_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate board-only coverage into source-bound review candidates."""
    if report is None:
        return ()
    coverage = report.board_only_footprint_coverage
    if coverage.status == "DISABLED":
        return ()
    if coverage.status == "BLOCKED":
        return (
            Candidate(
                rule_id="pcb.board_only_footprint",
                subject="native schematic-to-PCB reference comparison unavailable",
                message=(
                    "The source-bound schematic and native PCB footprint references could not be "
                    "compared. No conclusion about board-only footprints is available."
                ),
                evidence={
                    "coverage_issue": (coverage.issue or "unavailable",),
                    "netlist_sha256": (
                        () if report.netlist_sha256 is None else (report.netlist_sha256,)
                    ),
                    "board_path": (() if report.board_path is None else (report.board_path,)),
                    "board_sha256": (() if report.board_sha256 is None else (report.board_sha256,)),
                    "snapshot_sha256": (
                        () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
                    ),
                },
            ),
        )

    return tuple(
        Candidate(
            rule_id="pcb.board_only_footprint",
            subject=f"{item.reference}: PCB footprint has no schematic counterpart",
            message=(
                "This native PCB footprint reference is absent from the source-bound schematic. "
                "It may be an intentional mechanical, fabrication, or board-only item; confirm "
                "that it is deliberate or add its schematic counterpart. This comparison does "
                "not infer electrical role, assembly state, or manufacturing intent."
            ),
            evidence={
                "reference": (item.reference,),
                "footprint": (item.footprint,),
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
        for item in coverage.footprints
    )
