"""Source-bound evidence for reviewed unanchored connector assignments."""

from __future__ import annotations

from dataclasses import dataclass

from .connector_coverage import (
    connector_peer_assignment_groups_by_reference,
    source_matched_connector_peer_assignment_groups,
)
from .connector_coverage_models import ConnectorCoverageReport
from .connector_footprint_peer_pin_types import (
    ConnectorFootprintPeerPinDivergence,
    ConnectorFootprintPeerPinScan,
)
from .connector_identity import partition_peer_assignments, pin_function_is_generic
from .design_lint_connector_unanchored_source_evidence import (
    validate_current_unanchored_peer_contacts,
)
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate, CandidateEvidenceProjection

RULE_ID: DesignLintRuleId = "connector.footprint_peer_pin_unanchored_assignment_divergence"


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredAssignmentEvidence:
    """A reviewed peer-scope divergence tied to its current scan and coverage report."""

    scan: ConnectorFootprintPeerPinScan
    coverage: ConnectorCoverageReport
    divergence: ConnectorFootprintPeerPinDivergence

    def __post_init__(self) -> None:
        _validate_current_unanchored_assignment_evidence(self)

    @classmethod
    def from_scan(
        cls,
        *,
        scan: ConnectorFootprintPeerPinScan,
        coverage: ConnectorCoverageReport,
        divergence: ConnectorFootprintPeerPinDivergence,
    ) -> ConnectorUnanchoredAssignmentEvidence:
        """Capture one reviewed generic split from the exact connector scan."""
        return cls(scan=scan, coverage=coverage, divergence=divergence)


def _validate_current_unanchored_assignment_evidence(
    source: ConnectorUnanchoredAssignmentEvidence,
) -> None:
    scan = source.scan
    item = source.divergence
    observed = scan.source.observed
    current_peer_groups = source_matched_connector_peer_assignment_groups(
        observed,
        source.coverage,
    )
    if connector_peer_assignment_groups_by_reference(current_peer_groups) != (
        connector_peer_assignment_groups_by_reference(scan.source.peer_assignment_groups)
    ):
        raise ValueError(
            "Unanchored assignment scan must retain current source-matched peer groups"
        )
    if not item.peer_assignment_group or not item.peer_assignment_basis:
        raise ValueError("Unanchored assignment evidence requires a reviewed peer group and basis")

    references, _ = validate_current_unanchored_peer_contacts(
        scan=scan,
        divergences=(item,),
        partial_opens=(),
        expected_peer_assignment_group=item.peer_assignment_group,
    )
    partitions = partition_peer_assignments(item.assignments, current_peer_groups)
    if (
        len(partitions) != 1
        or partitions[0].peer_assignment_group != item.peer_assignment_group
        or partitions[0].peer_assignment_basis != item.peer_assignment_basis
        or dict(partitions[0].assignments_by_pin) != dict(item.assignments)
    ):
        raise ValueError("Unanchored assignment evidence must match its current reviewed scope")
    if (
        not pin_function_is_generic(item.pin_function)
        or item.common_anchor_pin_numbers
        or len(item.assignments) < 2
        or len(references) != len(item.assignments)
        or any(len(nets) != 1 for nets in item.assignments.values())
        or len({nets[0] for nets in item.assignments.values()}) < 2
    ):
        raise ValueError("Reviewed unanchored assignment evidence must retain the current split")


def project_connector_unanchored_assignment_evidence(
    source: ConnectorUnanchoredAssignmentEvidence,
) -> CandidateEvidenceProjection:
    """Project stable lint evidence fields from the current typed source."""
    _validate_current_unanchored_assignment_evidence(source)
    item = source.divergence
    evidence: dict[str, tuple[str, ...]] = {
        "value": (item.value,),
        "footprint": (item.footprint,),
        "pin_number": (item.pin_number,),
        "pin_function": (item.pin_function,),
        "assignments": tuple(
            f"{pin}={nets[0]}"
            for pin, nets in sorted(
                item.assignments.items(), key=lambda pair: (pair[0].casefold(), pair[0])
            )
        ),
        "symbols": item.symbols,
        "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
        "peer_assignment_group": (item.peer_assignment_group or "",),
        "peer_assignment_basis": item.peer_assignment_basis,
    }
    return CandidateEvidenceProjection(rule_id=RULE_ID, evidence=evidence)


@dataclass(frozen=True, slots=True)
class ConnectorUnanchoredAssignmentCandidate(Candidate):
    """Review prompt whose evidence retains current native and mapped sources."""

    source_evidence: ConnectorUnanchoredAssignmentEvidence

    @classmethod
    def from_source_evidence(
        cls,
        source_evidence: ConnectorUnanchoredAssignmentEvidence,
    ) -> ConnectorUnanchoredAssignmentCandidate:
        projection = project_connector_unanchored_assignment_evidence(source_evidence)
        item = source_evidence.divergence
        return cls(
            rule_id=projection.rule_id,
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
            message=(
                "Fitted connector aliases with the same value, footprint, complete pin inventory, "
                "and native pin metadata assign this generic contact to different nets in one "
                "current source-matched peer group, but have no shared-net anchor. Review the "
                "approved pinouts and intended port design. The peer group scopes comparison; "
                "it does not say the nets must match, and this finding does not establish that "
                "the contacts should be joined."
            ),
            evidence=projection.evidence,
            source_evidence=source_evidence,
        )

    def __post_init__(self) -> None:
        Candidate.__post_init__(self)
        projection = project_connector_unanchored_assignment_evidence(self.source_evidence)
        if self.rule_id != projection.rule_id or self.evidence != projection.evidence:
            raise ValueError(
                "Unanchored assignment fields must match their current source projection"
            )
