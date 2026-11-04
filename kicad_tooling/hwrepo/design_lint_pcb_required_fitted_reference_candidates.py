"""Review prompts for project-required PCB references that are not fitted."""

from __future__ import annotations

from .design_lint_pcb_required_fitted_candidate_evidence import (
    PcbBlockedRequiredFittedReferenceCandidate,
    PcbBlockedRequiredFittedReferenceEvidence,
    PcbRequiredFittedReferenceCandidate,
    PcbRequiredFittedReferenceEvidence,
)
from .design_lint_types import Candidate
from .pcb_component_inventory_models import (
    PcbComponentInventoryCoverageReport,
    PcbComponentInventorySourceReceipt,
)


def pcb_required_fitted_reference_candidates(
    report: PcbComponentInventoryCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Translate explicit fitted-reference requirements into exact review findings."""
    if report is None:
        return ()
    coverage = report.required_fitted_reference_coverage
    if coverage.status == "DISABLED":
        return ()
    if coverage.status == "BLOCKED":
        return (
            PcbBlockedRequiredFittedReferenceCandidate.from_source_evidence(
                PcbBlockedRequiredFittedReferenceEvidence(report),
                subject="project-required fitted-reference comparison unavailable",
                message=(
                    "The configured fitted-reference requirement could not be checked against "
                    "source-bound native schematic and PCB evidence. No conclusion is available."
                ),
            ),
        )

    receipt = PcbComponentInventorySourceReceipt.from_coverage_report(report)
    return tuple(
        PcbRequiredFittedReferenceCandidate.from_source_evidence(
            PcbRequiredFittedReferenceEvidence(
                observation=item,
                coverage=coverage,
                receipt=receipt,
                variant_population=report.variant_population,
            ),
            subject=(
                f"{item.reference}: required fitted component does not match source"
                if item.variant is None
                else f"{item.reference} in variant '{item.variant}': required fitted component does not match source"
            ),
            message=(
                "The project explicitly requires this reference to be fitted with the declared "
                "identity. Review the listed schematic and PCB differences, then correct the "
                "sources or update the independently approved requirement. This check does not "
                "infer assembly intent from similar components."
            ),
        )
        for item in coverage.mismatches
    )
