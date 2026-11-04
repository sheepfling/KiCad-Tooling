"""Build RC-filter coverage review candidates."""

from __future__ import annotations

from .design_lint_rc_filter_candidate_evidence import (
    RcFilterCandidate,
    RcFilterFindingEvidence,
)
from .design_lint_types import Candidate
from .rc_filter_models import RcFilterCoverageReport


def rc_filter_candidates(
    rc_filter_coverage: RcFilterCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if rc_filter_coverage is not None and rc_filter_coverage.status in {
        "COMPLETE",
        "INCOMPLETE",
    }:
        for entry in rc_filter_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            found.append(
                RcFilterCandidate.from_source_evidence(
                    RcFilterFindingEvidence(report=rc_filter_coverage, entry=entry),
                    subject=f"{entry.id}: mapped first-order RC low-pass filter",
                    message=(
                        "The source-bound resistor/capacitor identity, series/shunt topology, "
                        "nominal values, or calculated corner differs from the project-authored "
                        "requirement. Review the schematic and intended source/load conditions."
                    ),
                )
            )
    return tuple(found)
