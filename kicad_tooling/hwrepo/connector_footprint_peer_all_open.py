"""Eligibility and candidate creation for all-open footprint-alias contacts."""

from __future__ import annotations

from collections.abc import Mapping

from .connector_footprint_peer_pin_types import ConnectorFootprintPeerPinAllOpen
from .connector_identity import pin_function_is_generic

GENERIC_ALL_OPEN_PIN_TYPES = frozenset(
    {
        "passive",
        "input",
        "output",
        "bidirectional",
        "tri_state",
        "open_collector",
        "open_emitter",
    }
)


def generic_footprint_peer_all_open_candidate(
    *,
    footprint: str,
    value: str,
    pin_number: str,
    pin_function: str,
    pin_electrical_type: str,
    assignments: Mapping[str, tuple[str, ...]],
    symbols: tuple[str, ...],
    common_anchor_pin_numbers: tuple[str, ...],
    peer_assignment_group: str | None,
    peer_assignment_basis: tuple[str, ...],
) -> ConnectorFootprintPeerPinAllOpen | None:
    """Build an opt-in prompt from an anchor or a current reviewed peer scope.

    Callers must pass only source-matched peer-assignment groups. The group
    scopes comparison and does not establish that the contacts must connect.
    """
    electrical_type = pin_electrical_type.strip().casefold()
    if (
        not pin_function_is_generic(pin_function)
        or electrical_type not in GENERIC_ALL_OPEN_PIN_TYPES
        or any(assignments.values())
        or not assignments
        or (not common_anchor_pin_numbers and peer_assignment_group is None)
    ):
        return None
    return ConnectorFootprintPeerPinAllOpen(
        footprint=footprint,
        value=value,
        pin_number=pin_number,
        pin_function=pin_function,
        assignments=dict(sorted(assignments.items())),
        symbols=symbols,
        common_anchor_pin_numbers=common_anchor_pin_numbers,
        peer_assignment_group=peer_assignment_group,
        peer_assignment_basis=peer_assignment_basis,
    )
