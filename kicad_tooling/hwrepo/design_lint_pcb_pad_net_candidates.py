"""Finding translation for schematic-to-PCB pad net assignment comparison."""

from __future__ import annotations

from .design_lint_pcb_pad_net_candidate_evidence import (
    PcbBlockedPadNetComparisonCandidate,
    PcbBlockedPadNetComparisonEvidence,
    PcbPadNetMismatchCandidate,
    PcbPadNetMismatchEvidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)


def pcb_pad_net_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate pad-net comparison gaps and mismatches into review candidates."""
    if report is None or report.pad_net_comparison_status in {"NOT_APPLICABLE", "DISABLED"}:
        return ()
    receipt = PcbComponentInventorySourceReceipt.from_coverage_report(report)
    if report.pad_net_comparison_status == "BLOCKED":
        return (
            PcbBlockedPadNetComparisonCandidate.from_source_evidence(
                PcbBlockedPadNetComparisonEvidence(
                    issue=report.pad_net_comparison_issue or "unavailable",
                    receipt=receipt,
                    inventory_status=report.status,
                ),
                subject="schematic-to-PCB pad net comparison unavailable",
                message=(
                    "Source-bound schematic pin assignments could not be compared with native PCB "
                    "pad assignments. No pin-to-pad net consistency conclusion is available."
                ),
            ),
        )

    return tuple(
        PcbPadNetMismatchCandidate.from_source_evidence(
            PcbPadNetMismatchEvidence(observation=item, receipt=receipt),
            subject=f"{item.reference}.{item.pin}: schematic and PCB net assignments differ",
            message=(
                "The schematic pin and same-numbered PCB pad have different source net "
                "assignments. Review the intended mapping and update the appropriate CAD source. "
                "This exact reference/pin comparison does not infer peer-pin bonding or prove "
                "physical copper continuity."
            ),
        )
        for item in report.pad_net_mismatches
    )
