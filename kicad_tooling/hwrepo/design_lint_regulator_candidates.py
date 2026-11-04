"""Build regulator-feedback coverage review candidates."""

from __future__ import annotations

from .design_lint_regulator_candidate_evidence import (
    RegulatorFeedbackCandidate,
    RegulatorFeedbackFindingEvidence,
)
from .design_lint_types import Candidate
from .regulator_feedback_models import RegulatorFeedbackCoverageReport


def regulator_feedback_candidates(
    regulator_feedback_coverage: RegulatorFeedbackCoverageReport | None,
) -> tuple[Candidate, ...]:
    found: list[Candidate] = []
    if regulator_feedback_coverage is not None and regulator_feedback_coverage.status in {
        "COMPLETE",
        "INCOMPLETE",
    }:
        for entry in regulator_feedback_coverage.entries:
            if entry.status == "COMPLETE":
                continue
            found.append(
                RegulatorFeedbackCandidate.from_source_evidence(
                    RegulatorFeedbackFindingEvidence(
                        report=regulator_feedback_coverage,
                        entry=entry,
                    ),
                    subject=f"{entry.regulator_reference}: mapped feedback divider",
                    message=(
                        "The source-bound regulator identity, two-resistor feedback topology, "
                        "nominal values, or calculated output range differs from the "
                        "project-authored requirement. Review the device data sheet and pin map."
                    ),
                )
            )
    return tuple(found)
