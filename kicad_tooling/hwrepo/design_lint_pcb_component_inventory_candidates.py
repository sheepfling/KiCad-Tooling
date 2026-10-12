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
        candidates = [
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
            Candidate(
                rule_id="pcb.schematic_pcb_dnp_mismatch",
                subject="schematic and PCB population comparison unavailable",
                message=(
                    "The source-bound schematic DNP state could not be compared with the native PCB. "
                    "No population-consistency conclusion is available."
                ),
                evidence={
                    "coverage_issue": (report.issue or "unavailable",),
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
        ]
        if report.value_comparison_status == "BLOCKED":
            candidates.append(
                Candidate(
                    rule_id="pcb.schematic_pcb_value_mismatch",
                    subject="schematic and PCB component value comparison unavailable",
                    message=(
                        "The source-bound schematic and native PCB value fields could not be "
                        "compared. No value-consistency conclusion is available."
                    ),
                    evidence={
                        "coverage_issue": (
                            report.value_comparison_issue or report.issue or "unavailable",
                        ),
                        "netlist_sha256": (
                            () if report.netlist_sha256 is None else (report.netlist_sha256,)
                        ),
                        "board_path": (() if report.board_path is None else (report.board_path,)),
                        "board_sha256": (
                            () if report.board_sha256 is None else (report.board_sha256,)
                        ),
                        "snapshot_sha256": (
                            () if report.snapshot_sha256 is None else (report.snapshot_sha256,)
                        ),
                        "snapshot_schema": (
                            () if report.snapshot_schema is None else (report.snapshot_schema,)
                        ),
                    },
                )
            )
        return tuple(candidates)
    candidates = [
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
    ]
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_component_inventory",
            subject=f"{item.reference}: schematic and PCB footprint identities differ",
            message=(
                "The schematic assigns a different footprint identity from the source-bound PCB. "
                "Confirm the intended package or document the approved alternate; differing IDs "
                "can be intentional, and this exact-name comparison does not establish pad or "
                "geometry equivalence."
            ),
            evidence={
                "reference": (item.reference,),
                "assigned_footprint": (item.assigned_footprint,),
                "placed_footprint": (item.placed_footprint,),
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
        for item in report.footprint_mismatches
    )
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_pcb_dnp_mismatch",
            subject=f"{item.reference}: schematic and PCB DNP states differ",
            message=(
                "The schematic and placed PCB footprint disagree whether this component is marked "
                "DNP. Confirm the intended assembly variant and align the two CAD records. This "
                "compares CAD flags only; it does not establish physical population."
            ),
            evidence={
                "reference": (item.reference,),
                "schematic_dnp": (str(item.schematic_dnp).lower(),),
                "board_dnp": (str(item.board_dnp).lower(),),
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
        for item in report.population_mismatches
    )
    if report.value_comparison_status == "BLOCKED":
        candidates.append(
            Candidate(
                rule_id="pcb.schematic_pcb_value_mismatch",
                subject="native PCB footprint values unavailable",
                message=(
                    "The source-bound native PCB snapshot does not provide the footprint value "
                    "fields required for comparison. No value-consistency conclusion is available."
                ),
                evidence={
                    "coverage_issue": (
                        report.value_comparison_issue or "value comparison unavailable",
                    ),
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
        )
    candidates.extend(
        Candidate(
            rule_id="pcb.schematic_pcb_value_mismatch",
            subject=f"{item.reference}: schematic and PCB value fields differ",
            message=(
                "The schematic value and placed PCB footprint value differ as text. Review which "
                "value should appear in the fabrication source; this comparison does not establish "
                "electrical equivalence, part identity, physical population, or assembly intent."
            ),
            evidence={
                "reference": (item.reference,),
                "schematic_value": (item.schematic_value,),
                "board_value": (item.board_value,),
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
        for item in report.value_mismatches
    )
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))
