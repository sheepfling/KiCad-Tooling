"""Review generic component peer pins open on only part of a fitted group."""

from __future__ import annotations

from .component_peer_pin_identity import component_peer_pin_identity_context
from .component_peer_pin_scan import PeerPinAssignmentScan
from .design_lint_types import Candidate


def mixed_open_generic_component_peer_pin_candidates(
    scan: PeerPinAssignmentScan,
) -> tuple[Candidate, ...]:
    """Prompt when two peers agree on one net and another equivalent pin is open."""
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
        (
            subject_identity,
            identity_text,
            independent_net_text,
            identity_evidence,
        ) = component_peer_pin_identity_context(group)
        function = group.pin_function or ""
        candidates.append(
            Candidate(
                rule_id="component.generic_peer_pin_mixed_open",
                subject=(
                    f"{subject_identity} pin {group.pin_number} "
                    f"({function or 'generic'}): some fitted peers leave it open"
                ),
                message=(
                    f"Among fitted non-connector peers with {identity_text}, at least two "
                    f"matching generic pins share exact net {shared_assignment[0]!r} while "
                    f"{len(open_pins)} peer pin(s) are unassigned. Another pin shares an exact "
                    "single-net anchor across the group. Review whether the open assignments "
                    "are intentional or a connection is missing; peer identity and assignment "
                    f"consensus do not establish that the pins must connect, and {independent_net_text}."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_function": (function,),
                    "pin_electrical_type": (group.electrical_type,),
                    "assigned_pins": assigned_pins,
                    "unassigned_pins": open_pins,
                    "shared_assignment_net": shared_assignment,
                    "shared_anchor_contacts": group.shared_anchor_contacts,
                },
            )
        )
    return tuple(candidates)
