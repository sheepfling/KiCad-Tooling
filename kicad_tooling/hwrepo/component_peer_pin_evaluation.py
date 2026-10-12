"""Coordinate typed scans for component peer-pin lint coverage."""

from __future__ import annotations

from .component_peer_pin_assignment_outlier import (
    scan_generic_component_peer_pin_assignment_outliers,
)
from .component_peer_pin_scan import (
    GENERIC_COMPONENT_MIXED_PIN_TYPES,
    GENERIC_COMPONENT_PIN_TYPES,
    ComponentPeerPinAssignmentScans,
    scan_component_peer_pin_assignments,
)
from .models import NetlistContract


def component_peer_pin_assignment_scans(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> ComponentPeerPinAssignmentScans:
    """Return bounded applicability scans for all native peer-pin checks."""
    return ComponentPeerPinAssignmentScans(
        power_output=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"power_out"}),
        ),
        signal_output=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"output"}),
        ),
        signal_input=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"input", "input_low"}),
            require_pin_functions=True,
        ),
        bidirectional=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=frozenset({"bidirectional"}),
            require_pin_functions=True,
        ),
        generic_assignment_outlier=scan_generic_component_peer_pin_assignment_outliers(
            observed,
            declared_references,
        ),
        generic_all_open=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=GENERIC_COMPONENT_PIN_TYPES,
            require_generic_pin_functions=True,
            assignment_pattern="all_open",
            require_shared_anchor=True,
        ),
        generic_partial_open=scan_component_peer_pin_assignments(
            observed,
            declared_references,
            electrical_types=GENERIC_COMPONENT_MIXED_PIN_TYPES,
            require_generic_pin_functions=True,
            require_shared_anchor=True,
            minimum_peer_count=3,
            minimum_assigned_peer_count=2,
            require_assigned_peers_on_same_net=True,
        ),
    )
