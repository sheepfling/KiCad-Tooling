"""Adapt bounded footprint-alias pin scans to review-only lint candidates."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_peer_pins import (
    ConnectorFootprintPeerPinScan,
    scan_connector_footprint_peer_pin_assignments,
)
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
    divergence_candidates = tuple(
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
    return (
        *divergence_candidates,
        *_footprint_peer_pin_open_candidates(scan),
    )


def _footprint_peer_pin_open_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Review generic pin contacts left open on a subset of footprint peers."""
    return tuple(
        Candidate(
            rule_id="connector.footprint_peer_pin_open_outlier",
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
            message=(
                "Fitted connector instances with distinct native symbols share the same value, "
                "footprint, complete pin inventory, and matching pin-function and electrical-type "
                "metadata. This generic contact is assigned on some peers and unassigned on others, "
                "while a separate contact has one common assigned net. Review the approved pinout "
                "for an intentional open or a missing connection; similarity does not prove that "
                "this contact must connect."
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
                    f"{pin}={','.join(nets) if nets else '<unassigned>'}"
                    for pin, nets in item.assignments.items()
                ),
                "open_pins": item.open_pins,
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
        for item in scan.open_outliers
    )
