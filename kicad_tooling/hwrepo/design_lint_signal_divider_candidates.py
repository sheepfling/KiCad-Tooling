"""Build candidates for mapped signal dividers outside authored input limits."""

from __future__ import annotations

from .design_lint_signal_divider_evidence import (
    SignalDividerCandidate,
    SignalDividerFindingEvidence,
)
from .design_lint_types import Candidate
from .signal_divider_models import SignalDividerCoverageReport


def signal_divider_candidates(
    coverage: SignalDividerCoverageReport | None,
) -> tuple[Candidate, ...]:
    """Emit one candidate for each mapped signal divider needing review."""
    if coverage is None or coverage.status not in {"COMPLETE", "INCOMPLETE"}:
        return ()
    candidates: list[Candidate] = []
    for entry in coverage.entries:
        if entry.status == "COMPLETE":
            continue
        candidates.append(
            SignalDividerCandidate.from_source_evidence(
                SignalDividerFindingEvidence(report=coverage, entry=entry),
                subject=f"{entry.receiver_reference}: mapped signal-input divider",
                message=(
                    "The source-bound divider identity, two-resistor topology, nominal values, or "
                    "calculated input range differs from the project-authored requirement. "
                    "Review the exact source and input limits."
                ),
            )
        )
    return tuple(candidates)
