"""Adapt bounded footprint-alias pin scans to review-only lint candidates."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_named_power_input_divergence import (
    evaluate_footprint_named_power_input_assignment_divergence,
)
from .connector_footprint_named_power_output_divergence import (
    evaluate_footprint_named_power_output_assignment_divergence,
)
from .connector_footprint_named_signal_divergence import (
    evaluate_footprint_named_signal_assignment_divergence,
)
from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinScan
from .connector_footprint_peer_pins import (
    scan_connector_footprint_peer_pin_assignments,
)
from .connector_footprint_power_input import footprint_named_power_input_open_outlier_candidates
from .connector_footprint_power_output import (
    footprint_named_power_output_open_outlier_candidates,
)
from .connector_footprint_signal_input import (
    footprint_named_signal_input_open_outlier_candidates,
)
from .connector_footprint_signal_output import (
    footprint_named_signal_output_open_outlier_candidates,
)
from .connector_identity import pin_function_is_generic
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
                "pin_function": (item.pin_function,),
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
    named_signal_divergence = evaluate_footprint_named_signal_assignment_divergence(scan)
    named_power_input_divergence = evaluate_footprint_named_power_input_assignment_divergence(scan)
    named_power_output_divergence = evaluate_footprint_named_power_output_assignment_divergence(
        scan
    )
    return (
        *divergence_candidates,
        *named_signal_divergence.candidates,
        *named_power_input_divergence.candidates,
        *named_power_output_divergence.candidates,
        *_footprint_peer_pin_open_candidates(scan),
        *footprint_named_power_input_open_outlier_candidates(scan),
        *footprint_named_signal_input_open_outlier_candidates(scan),
        *footprint_named_power_output_open_outlier_candidates(scan),
        *footprint_named_signal_output_open_outlier_candidates(scan),
        *_footprint_peer_pin_all_open_candidates(scan),
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
                "pin_function": (item.pin_function,),
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
        if pin_function_is_generic(item.pin_function)
    )


def _footprint_peer_pin_all_open_candidates(
    scan: ConnectorFootprintPeerPinScan,
) -> tuple[Candidate, ...]:
    """Create opt-in review prompts for generic contacts open on every alias peer."""
    return tuple(
        Candidate(
            rule_id="connector.footprint_peer_pin_all_open",
            subject=f"{item.value} [{item.footprint}] pin {item.pin_number}",
            message=(
                "Fitted connector instances with distinct native symbols share the same value, "
                "footprint, complete pin inventory, and matching pin-function and electrical-type "
                "metadata. This generic contact is unassigned on every compared peer, while a "
                "separate contact has one common assigned net. Review the approved pinout for an "
                "intentionally unused contact or a missing connection; these similarity clues do "
                "not establish that the contact must connect."
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
                "pin_function": (item.pin_function,),
                "assignments": tuple(
                    f"{pin}={','.join(nets) if nets else '<unassigned>'}"
                    for pin, nets in item.assignments.items()
                ),
                "open_pins": tuple(item.assignments),
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
        for item in scan.all_open
    )
