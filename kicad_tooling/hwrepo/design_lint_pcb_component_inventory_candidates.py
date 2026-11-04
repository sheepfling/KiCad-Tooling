"""PCB component inventory finding translation for design-lint reports."""

from __future__ import annotations

from .design_lint_pcb_inventory_candidate_evidence import (
    PcbInventoryCandidate,
    PcbInventorySourceEvidence,
)
from .design_lint_pcb_population_candidate_evidence import (
    PcbBlockedVariantPopulationCandidate,
    PcbBlockedVariantPopulationEvidence,
    PcbPopulationCandidate,
    PcbPopulationMismatchEvidence,
    project_named_variant_population_evidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)


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
    source_receipt = PcbComponentInventorySourceReceipt(
        netlist_sha256=report.netlist_sha256,
        board_path=report.board_path,
        board_sha256=report.board_sha256,
        snapshot_sha256=report.snapshot_sha256,
        snapshot_schema=report.snapshot_schema,
        kicad_version=report.kicad_version,
        image=report.image,
        probe_sha256=report.probe_sha256,
    )
    candidates: list[Candidate] = [
        PcbInventoryCandidate.from_source_evidence(
            PcbInventorySourceEvidence(
                observation=item,
                receipt=source_receipt,
            ),
            subject=f"{item.reference}: schematic footprint absent from PCB",
            message=(
                "This fitted schematic component has an assigned footprint, but the source-bound "
                "native PCB snapshot has no footprint with the same reference. Confirm whether "
                "the component is intentionally off-board; otherwise restore its board placement. "
                "This check does not infer electrical role, assembly intent, or manufacturability."
            ),
        )
        for item in report.missing_placements
    ]
    candidates.extend(
        PcbInventoryCandidate.from_source_evidence(
            PcbInventorySourceEvidence(
                observation=item,
                receipt=source_receipt,
            ),
            subject=f"{item.reference}: schematic and PCB footprint identities differ",
            message=(
                "The schematic assigns a different footprint identity from the source-bound PCB. "
                "Confirm the intended package or document the approved alternate; differing IDs "
                "can be intentional, and this exact-name comparison does not establish pad or "
                "geometry equivalence."
            ),
        )
        for item in report.footprint_mismatches
    )
    candidates.extend(
        PcbPopulationCandidate.from_source_evidence(
            PcbPopulationMismatchEvidence(
                observation=item,
                receipt=source_receipt,
                variant_population=report.variant_population,
            ),
            subject=(
                f"{item.reference}: schematic and PCB DNP states differ"
                if item.variant is None
                else f"{item.reference}: schematic and PCB DNP states differ in {item.variant}"
            ),
            message=(
                "The schematic and placed PCB footprint disagree whether this component is marked "
                "DNP. Confirm the intended assembly variant and align the two CAD records. This "
                "compares CAD flags only; it does not establish physical population."
            ),
        )
        for item in report.population_mismatches
    )
    if report.variant_population.status == "BLOCKED":
        variant_coverage = report.variant_population
        candidates.append(
            PcbBlockedVariantPopulationCandidate.from_source_evidence(
                PcbBlockedVariantPopulationEvidence(variant_coverage),
                subject="named variant DNP comparison unavailable",
                message=(
                    "The project declares one or more named variants, but source-bound schematic "
                    "and PCB exports could not be paired for every variant. No variant population "
                    "consistency conclusion is available."
                ),
            )
        )
    if report.value_comparison_status == "BLOCKED":
        candidates.append(
            Candidate(
                rule_id="pcb.schematic_pcb_value_mismatch",
                subject="native PCB footprint values unavailable",
                message=(
                    "Source-bound PCB value evidence is incomplete, including any declared named "
                    "variant exports. No value-consistency conclusion is available."
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
            subject=(
                f"{item.reference}: schematic and PCB value fields differ"
                if item.variant is None
                else f"{item.reference}: schematic and PCB value fields differ in {item.variant}"
            ),
            message=(
                "The same-name schematic and PCB variant value fields differ as text. Review which "
                "value should appear for this assembly variant. This comparison does not establish "
                "electrical equivalence, part identity, physical population, or assembly intent."
                if item.variant is not None
                else "The schematic value and placed PCB footprint value differ as text. Review which "
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
                **project_named_variant_population_evidence(
                    item.variant,
                    report.variant_population,
                ),
            },
        )
        for item in report.value_mismatches
    )
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))
