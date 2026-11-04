"""Build crystal-network coverage review candidates."""

from __future__ import annotations

from .crystal_network_models import CrystalNetworkCoverageReport
from .design_lint_crystal_candidate_evidence import (
    CrystalNetworkCandidate,
    CrystalNetworkFindingEvidence,
)
from .design_lint_types import Candidate


def crystal_network_candidates(
    crystal_network_coverage: CrystalNetworkCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if crystal_network_coverage is not None and crystal_network_coverage.status in {
        "COMPLETE",
        "INCOMPLETE",
    }:
        for entry in crystal_network_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            found.append(
                CrystalNetworkCandidate.from_source_evidence(
                    CrystalNetworkFindingEvidence(
                        report=crystal_network_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.oscillator_reference}: mapped crystal load network",
                    message=(
                        "The source-bound oscillator, resonator, load-capacitor topology, or "
                        "nominal load estimate differs from the project-authored requirement. "
                        "Review the exact pin map and device requirements."
                    ),
                )
            )
    return tuple(found)
