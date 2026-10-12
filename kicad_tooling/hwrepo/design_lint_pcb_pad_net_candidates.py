"""Finding translation for schematic-to-PCB pad net assignment comparison."""

from __future__ import annotations

from .design_lint_types import Candidate
from .pcb_component_inventory_models import PcbComponentInventoryCoverageReport

RULE_ID = "pcb.schematic_pcb_pad_net_mismatch"


def pcb_pad_net_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate pad-net comparison gaps and mismatches into review candidates."""
    if report is None or report.pad_net_comparison_status in {"NOT_APPLICABLE", "DISABLED"}:
        return ()
    if report.pad_net_comparison_status == "BLOCKED":
        return (
            Candidate(
                rule_id=RULE_ID,
                subject="schematic-to-PCB pad net comparison unavailable",
                message=(
                    "Source-bound schematic pin assignments could not be compared with native PCB "
                    "pad assignments. No pin-to-pad net consistency conclusion is available."
                ),
                evidence=_source_evidence(report)
                | {"coverage_issue": (report.pad_net_comparison_issue or "unavailable",)},
            ),
        )

    return tuple(
        Candidate(
            rule_id=RULE_ID,
            subject=f"{item.reference}.{item.pin}: schematic and PCB net assignments differ",
            message=(
                "The schematic pin and same-numbered PCB pad have different source net "
                "assignments. Review the intended mapping and update the appropriate CAD source. "
                "This exact reference/pin comparison does not infer peer-pin bonding or prove "
                "physical copper continuity."
            ),
            evidence=_source_evidence(report)
            | {
                "reference": (item.reference,),
                "pin": (item.pin,),
                "mismatch": (item.mismatch,),
                "schematic_net": (item.schematic_net or "unconnected",),
                "board_net": (item.board_net or "unassigned",),
            },
        )
        for item in report.pad_net_mismatches
    )


def _source_evidence(report: PcbComponentInventoryCoverageReport) -> dict[str, tuple[str, ...]]:
    return {
        "netlist_sha256": (report.netlist_sha256 or "unavailable",),
        "board_path": (report.board_path or "unavailable",),
        "board_sha256": (report.board_sha256 or "unavailable",),
        "snapshot_sha256": (report.snapshot_sha256 or "unavailable",),
        "snapshot_schema": (report.snapshot_schema or "unavailable",),
        "kicad_version": (report.kicad_version or "unavailable",),
        "image": (report.image or "unavailable",),
        "probe_sha256": (report.probe_sha256 or "unavailable",),
    }
