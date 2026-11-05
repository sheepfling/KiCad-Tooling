"""Review unanchored generic pin splits in source-matched connector peer groups."""

from __future__ import annotations

from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_identity import pin_function_is_generic
from .design_lint_connector_unanchored_assignment_evidence import (
    ConnectorUnanchoredAssignmentCandidate,
    ConnectorUnanchoredAssignmentEvidence,
)
from .design_lint_types import Candidate


def reviewed_unanchored_connector_alias_divergences(
    scan: ConnectorFootprintPeerPinScan,
    coverage: ConnectorCoverageReport | None = None,
) -> tuple[Candidate, ...]:
    """Prompt only for complete generic pin splits scoped by current project review."""
    if coverage is None:
        return ()
    candidates: list[Candidate] = []
    for item in scan.unanchored_divergences:
        if (
            item.peer_assignment_group is None
            or not item.peer_assignment_basis
            or item.common_anchor_pin_numbers
            or not pin_function_is_generic(item.pin_function)
            or len(item.assignments) < 2
            or any(len(nets) != 1 for nets in item.assignments.values())
            or len({nets[0] for nets in item.assignments.values()}) < 2
        ):
            continue
        source_evidence = ConnectorUnanchoredAssignmentEvidence.from_scan(
            scan=scan,
            coverage=coverage,
            divergence=item,
        )
        candidates.append(
            ConnectorUnanchoredAssignmentCandidate.from_source_evidence(source_evidence)
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.subject.casefold(),
                tuple(candidate.evidence["assignments"]),
                tuple(candidate.evidence["symbols"]),
            ),
        )
    )
