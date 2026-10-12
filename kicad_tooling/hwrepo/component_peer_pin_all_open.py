"""Review prompts for generic component peer pins left open on every copy."""

from __future__ import annotations

from .component_peer_pin_scan import PeerPinAssignmentScan
from .design_lint_types import Candidate


def all_open_generic_component_peer_pin_candidates(
    scan: PeerPinAssignmentScan,
) -> tuple[Candidate, ...]:
    """Build opt-in prompts from complete, anchored all-open peer observations."""
    candidates: list[Candidate] = []
    for group in scan.outliers:
        if not group.shared_anchor_contacts:
            continue
        open_pins = tuple(pin for pin, nets in group.assignments.items() if not nets)
        if len(open_pins) < 2 or len(open_pins) != len(group.assignments):
            continue
        if group.peer_identity_basis == "part_id":
            identity = f"PART_ID {group.peer_identity}"
            identity_description = (
                f"the same native PART_ID {group.peer_identity!r} across distinct native symbols"
            )
            identity_evidence = {
                "peer_group_basis": ("part_id",),
                "peer_group_identity": (group.peer_identity,),
                "peer_group_symbols": group.peer_symbols,
            }
        else:
            identity = group.peer_identity
            identity_description = f"the exact native symbol {group.peer_identity!r}"
            identity_evidence = {
                "peer_group_basis": ("exact_symbol",),
                "peer_group_identity": (group.peer_identity,),
                "peer_group_symbols": group.peer_symbols,
                "symbol": (group.peer_identity,),
            }
        function = group.pin_function or ""
        candidates.append(
            Candidate(
                rule_id="component.generic_peer_pin_all_open",
                subject=(
                    f"{identity} pin {group.pin_number} ({function or 'generic'}): "
                    "all fitted peers leave this pin open"
                ),
                message=(
                    f"A generic {group.electrical_type} pin is unassigned on every fitted "
                    f"non-connector peer with {identity_description}, while another pin has "
                    "the same exact net assignment across the group. Review the approved part "
                    "requirements for an intentionally unused pin or a missing connection. "
                    "Matching symbol or part identity and shared peer wiring do not establish "
                    "that this pin must connect."
                ),
                evidence={
                    **group.assignments,
                    **identity_evidence,
                    "pin_number": (group.pin_number,),
                    "pin_function": (function,),
                    "pin_electrical_type": (group.electrical_type,),
                    "unassigned_pins": open_pins,
                    "shared_anchor_contacts": group.shared_anchor_contacts,
                },
            )
        )
    return tuple(candidates)
