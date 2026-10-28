"""Review generic component peer pins that differ from a strict majority."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from .component_peer_pin_scan import (
    GENERIC_COMPONENT_MIXED_PIN_TYPES,
    PeerPinAssignmentScan,
    scan_component_peer_pin_assignments,
)
from .models import NetlistContract


def _strict_majority_assignment_outlier(
    assignments: Mapping[str, tuple[str, ...]], peers: tuple[str, ...]
) -> tuple[str, tuple[str, ...]] | None:
    if any(len(nets) != 1 for nets in assignments.values()):
        return None
    net_counts = Counter(nets[0] for nets in assignments.values())
    ordered_counts = sorted(
        net_counts.items(), key=lambda item: (-item[1], item[0].casefold(), item[0])
    )
    if (
        len(ordered_counts) < 2
        or ordered_counts[0][1] < 2
        or ordered_counts[0][1] * 2 <= len(peers)
    ):
        return None
    majority_net = ordered_counts[0][0]
    outlier_pins = tuple(
        sorted(
            (pin for pin, nets in assignments.items() if nets[0] != majority_net),
            key=lambda pin: (pin.casefold(), pin),
        )
    )
    return majority_net, outlier_pins


def scan_generic_component_peer_pin_assignment_outliers(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> PeerPinAssignmentScan:
    """Find generic passive peers with a strict majority assignment.

    This review scan requires at least three fitted non-connector peers,
    a shared exact-net anchor on another pin, complete matching inventories,
    one unambiguous assignment per peer, and a generic target function. The
    majority is comparison context only; it does not define required wiring.
    """
    return scan_component_peer_pin_assignments(
        observed,
        declared_references,
        electrical_types=GENERIC_COMPONENT_MIXED_PIN_TYPES,
        require_generic_pin_functions=True,
        assignment_outlier_selector=_strict_majority_assignment_outlier,
        require_shared_anchor=True,
        minimum_peer_count=3,
    )
