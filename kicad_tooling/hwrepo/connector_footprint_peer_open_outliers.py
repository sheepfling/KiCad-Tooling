"""Construct typed open-contact evidence for connector footprint peers."""

from __future__ import annotations

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinOpenOutlier


def connector_footprint_peer_open_outlier(
    *,
    footprint: str,
    value: str,
    pin_number: str,
    pin_function: str,
    pin_electrical_type: str,
    assignments: dict[str, tuple[str, ...]],
    symbols: tuple[str, ...],
    common_anchor_pin_numbers: tuple[str, ...],
    peer_assignment_group: str | None,
    peer_assignment_basis: tuple[str, ...],
) -> ConnectorFootprintPeerPinOpenOutlier:
    """Build one stable open-contact record from an already bounded peer scope."""
    return ConnectorFootprintPeerPinOpenOutlier(
        footprint=footprint,
        value=value,
        pin_number=pin_number,
        pin_function=pin_function,
        pin_electrical_type=pin_electrical_type,
        assignments=assignments,
        open_pins=tuple(pin for pin, nets in assignments.items() if not nets),
        symbols=symbols,
        common_anchor_pin_numbers=common_anchor_pin_numbers,
        peer_assignment_group=peer_assignment_group,
        peer_assignment_basis=peer_assignment_basis,
    )
