"""Adapt bounded footprint-alias pin scans to review-only lint candidates."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_peer_pins import scan_connector_footprint_peer_pin_assignments
from .design_lint_types import Candidate
from .models import NetlistContract


def connector_footprint_peer_pin_candidates(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[Candidate, ...]:
    """Create review prompts when footprint-similar connector pin assignments differ."""
    scan = scan_connector_footprint_peer_pin_assignments(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    return tuple(
        Candidate(
            rule_id="connector.footprint_peer_pin_assignment_divergence",
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
            message=(
                "Fitted connector instances with distinct native symbols share the same value, "
                "footprint, complete pin inventory, and matching pin-function and electrical-type "
                "metadata. Their generic contacts use different assigned nets while another "
                "contact shares a net. Review the approved pinout and intended port isolation; "
                "these similarity clues do not prove the contacts should be common."
                + (
                    " The comparison is scoped to a source-reviewed peer-assignment group."
                    if item.peer_assignment_group is not None
                    else ""
                )
            ),
            evidence={
                "value": (item.value,),
                "footprint": (item.footprint,),
                "pin_number": (item.pin_number,),
                "assignments": tuple(
                    f"{pin}={','.join(nets)}" for pin, nets in item.assignments.items()
                ),
                "symbols": item.symbols,
                "common_anchor_pin_numbers": item.common_anchor_pin_numbers,
                **(
                    {}
                    if item.peer_assignment_group is None
                    else {
                        "peer_assignment_group": (item.peer_assignment_group,),
                        "peer_assignment_basis": item.peer_assignment_basis,
                    }
                ),
            },
        )
        for item in scan.divergences
    )
