"""Build protection-coverage review candidates."""

from __future__ import annotations

from .design_lint_interfaces_protection_capacitance import protection_capacitance_candidates
from .design_lint_protection_candidate_evidence import (
    ProtectionMismatchCandidate,
    ProtectionMismatchFindingEvidence,
    UnreviewedProtectionCandidate,
    UnreviewedProtectionFindingEvidence,
)
from .design_lint_types import Candidate
from .external_protection_models import ExternalProtectionCoverageReport


def protection_candidates(
    external_protection_coverage: ExternalProtectionCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if external_protection_coverage is not None and external_protection_coverage.status in {
        "COMPLETE",
        "INCOMPLETE",
        "UNDECLARED",
    }:
        for entry in external_protection_coverage.entries:
            if entry.status == "UNDECLARED":
                found.append(
                    UnreviewedProtectionCandidate.from_source_evidence(
                        UnreviewedProtectionFindingEvidence(
                            report=external_protection_coverage,
                            entry=entry,
                        ),
                        subject=(
                            f"{entry.connector_pin}: "
                            f"{entry.interface_signal or 'external interface signal'}"
                        ),
                        message=(
                            "This project-reviewed connector pin has no protection applicability "
                            "decision. Map the required protector channel or record a reasoned "
                            "not-required decision; the rule does not assume protection is needed."
                        ),
                    )
                )
            elif entry.status in {"INCOMPLETE", "STALE"}:
                found.append(
                    ProtectionMismatchCandidate.from_source_evidence(
                        ProtectionMismatchFindingEvidence(
                            report=external_protection_coverage,
                            entry=entry,
                        ),
                        subject=f"{entry.connector_pin}: mapped protection requirement",
                        message=(
                            "The project-mapped protection identity or pin/net assignment differs "
                            "from source-bound native evidence. Review the connector map and device "
                            "pinout."
                        ),
                    )
                )
    return (*found, *protection_capacitance_candidates(external_protection_coverage))
