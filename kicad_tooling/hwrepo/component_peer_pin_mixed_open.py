"""Review generic component peer pins open on only part of a fitted group."""

from __future__ import annotations

from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_scan import PeerPinAssignmentScan
from .design_lint_component_peer_open_candidate_evidence import (
    GenericComponentPeerOpenCandidate,
    GenericComponentPeerOpenScanEvidence,
)
from .design_lint_types import Candidate
from .netlist_contract_models import NetlistContract


def mixed_open_generic_component_peer_pin_candidates(
    scan: PeerPinAssignmentScan,
    *,
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[Candidate, ...]:
    """Prompt when two peers agree on one net and another equivalent pin is open."""
    source_scan = GenericComponentPeerOpenScanEvidence.from_scan(
        observed=observed,
        scan=scan,
        declared_references=declared_references,
        rule_id="component.generic_peer_pin_mixed_open",
    )
    candidates: list[Candidate] = []
    for group in scan.outliers:
        if len(group.assignments) < 3 or not group.shared_anchor_contacts:
            continue
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        assigned_pins = tuple(pin for pin, nets in group.assignments.items() if nets)
        if not open_pins or len(assigned_pins) < 2:
            continue
        assigned_nets = {group.assignments[pin] for pin in assigned_pins}
        if len(assigned_nets) != 1:
            continue
        shared_assignment = next(iter(assigned_nets))
        if len(shared_assignment) != 1:
            continue
        identity = component_peer_pin_identity_context(group)
        function = group.pin_function or ""
        candidates.append(
            GenericComponentPeerOpenCandidate.from_source_evidence(
                source_scan.for_outlier(group),
                subject=(
                    f"{identity.subject_identity} pin {group.pin_number} "
                    f"({function or 'generic'}): some fitted peers leave it open"
                ),
                message=(
                    "Among fitted non-connector peers with "
                    f"{identity.identity_description}, at least two "
                    f"matching generic pins share exact net {shared_assignment[0]!r} while "
                    f"{len(open_pins)} peer pin(s) are unassigned. Another pin shares an exact "
                    "single-net anchor across the group. Review whether the open assignments "
                    "are intentional or a connection is missing; peer identity and assignment "
                    "consensus do not establish that the pins must connect, and "
                    f"{identity.independent_net_note}."
                ),
            )
        )
    return tuple(candidates)
