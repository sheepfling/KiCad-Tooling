"""Translate authored connector signal-to-return distribution coverage."""

from __future__ import annotations

from .connector_return_distribution_models import ConnectorReturnDistributionCoverageReport
from .design_lint_return_distribution_candidate_evidence import (
    ConnectorReturnDistributionCandidate,
    ConnectorReturnDistributionFindingEvidence,
)
from .design_lint_types import Candidate


def return_distribution_candidates(
    connector_return_distribution: ConnectorReturnDistributionCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Build review candidates for explicit connector return-contact thresholds."""
    found: list[Candidate] = []
    if connector_return_distribution is not None and connector_return_distribution.status in {
        "COMPLETE",
        "INCOMPLETE",
    }:
        for entry in connector_return_distribution.entries:
            if entry.status not in {"OUT_OF_RANGE", "INCOMPLETE"}:
                continue
            found.append(
                ConnectorReturnDistributionCandidate.from_source_evidence(
                    ConnectorReturnDistributionFindingEvidence(
                        coverage=connector_return_distribution,
                        entry=entry,
                    ),
                    subject=(
                        f"{entry.connector_reference or entry.interface_id}: "
                        "reviewed return-contact distribution"
                    ),
                    message=(
                        "The explicitly role-classified interface is outside its project-authored "
                        "signal-to-return contact threshold or lacks complete role evidence. "
                        "Review the pin allocation; this ratio does not require returns to share "
                        "a net."
                    ),
                )
            )
    return tuple(found)
