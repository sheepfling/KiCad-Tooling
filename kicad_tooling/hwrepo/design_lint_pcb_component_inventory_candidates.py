"""PCB component inventory finding translation for design-lint reports."""

from __future__ import annotations

from typing import Literal

from .design_lint_pcb_blocked_inventory_evidence import (
    PcbBlockedComponentInventoryCandidate,
    PcbBlockedComponentInventoryEvidence,
    PcbBlockedPopulationCandidate,
)
from .design_lint_pcb_inventory_candidate_evidence import (
    PcbInventoryCandidate,
    PcbInventorySourceEvidence,
)
from .design_lint_pcb_population_candidate_evidence import (
    PcbBlockedVariantPopulationCandidate,
    PcbBlockedVariantPopulationEvidence,
    PcbPopulationCandidate,
    PcbPopulationMismatchEvidence,
)
from .design_lint_pcb_value_candidate_evidence import (
    PcbBlockedValueComparisonCandidate,
    PcbBlockedValueComparisonEvidence,
    PcbValueMismatchCandidate,
    PcbValueMismatchEvidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)


def pcb_component_inventory_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate source-bound PCB inventory, population, and value reports."""
    if report is None or report.status in {"NOT_APPLICABLE", "DISABLED"}:
        return ()
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
    if report.status == "BLOCKED":
        blocked_evidence = PcbBlockedComponentInventoryEvidence(report)
        candidates = [
            PcbBlockedComponentInventoryCandidate.from_source_evidence(
                blocked_evidence,
                subject="native PCB footprint inventory unavailable",
                message=(
                    "The source-bound PCB footprint inventory could not be compared with the "
                    "native schematic netlist. No placement conclusion is available."
                ),
            ),
            PcbBlockedPopulationCandidate.from_source_evidence(
                blocked_evidence,
                subject="schematic and PCB population comparison unavailable",
                message=(
                    "The source-bound schematic DNP state could not be compared with the native PCB. "
                    "No population-consistency conclusion is available."
                ),
            ),
        ]
        if report.value_comparison_status == "BLOCKED":
            candidates.append(
                _blocked_value_candidate(
                    receipt=source_receipt,
                    issue=report.value_comparison_issue or report.issue or "unavailable",
                    inventory_status="BLOCKED",
                    subject="schematic and PCB component value comparison unavailable",
                    message=(
                        "The source-bound schematic and native PCB value fields could not be "
                        "compared. No value-consistency conclusion is available."
                    ),
                )
            )
        return tuple(candidates)
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
            _blocked_value_candidate(
                receipt=source_receipt,
                issue=report.value_comparison_issue or "value comparison unavailable",
                inventory_status="COMPLETE",
                subject="native PCB footprint values unavailable",
                message=(
                    "Source-bound PCB value evidence is incomplete, including any declared named "
                    "variant exports. No value-consistency conclusion is available."
                ),
            )
        )
    candidates.extend(
        PcbValueMismatchCandidate.from_source_evidence(
            PcbValueMismatchEvidence(
                observation=item,
                receipt=source_receipt,
                variant_population=report.variant_population,
            ),
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
        )
        for item in report.value_mismatches
    )
    return tuple(sorted(candidates, key=lambda item: item.subject.casefold()))


def _blocked_value_candidate(
    *,
    receipt: PcbComponentInventorySourceReceipt,
    issue: str,
    inventory_status: Literal["BLOCKED", "COMPLETE"],
    subject: str,
    message: str,
) -> PcbBlockedValueComparisonCandidate:
    return PcbBlockedValueComparisonCandidate.from_source_evidence(
        PcbBlockedValueComparisonEvidence(
            issue=issue,
            receipt=receipt,
            inventory_status=inventory_status,
        ),
        subject=subject,
        message=message,
    )
