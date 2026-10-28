"""Shared source-bound grouping for named connector power-pin aliases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .connector_identity import (
    is_named_supply_function,
    is_return_function,
    pin_function_is_generic,
)
from .connector_peer_pin_scan import (
    ConnectorPartIdPeerPinGroup,
    scan_connector_part_id_peer_pins,
)
from .models import NetlistContract

ConnectorPowerElectricalType = Literal["power_in", "power_out"]


@dataclass(frozen=True, slots=True)
class ConnectorNamedPowerAliasPeer:
    group: ConnectorPartIdPeerPinGroup
    function: str
    symbols: tuple[str, ...]


def connector_named_power_alias_peers(
    observed: NetlistContract,
    electrical_type: ConnectorPowerElectricalType,
    declared_references: tuple[str, ...] = (),
    peer_assignment_groups: Mapping[str, tuple[str, str]] | None = None,
) -> tuple[ConnectorNamedPowerAliasPeer, ...]:
    """Return guarded, cross-symbol aliases for explicit unrecognized power pins."""
    symbols_by_reference = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    peers: list[ConnectorNamedPowerAliasPeer] = []
    scan = scan_connector_part_id_peer_pins(
        observed,
        declared_references,
        peer_assignment_groups,
    )
    for group in scan.pin_groups:
        function = group.pin_function.strip()
        if (
            group.pin_electrical_type.strip().casefold() != electrical_type
            or pin_function_is_generic(function)
            or is_named_supply_function(function)
            or is_return_function(function)
        ):
            continue

        references = {pin.rsplit(".", 1)[0].casefold() for pin in group.assignments}
        symbols = tuple(
            sorted(
                {
                    symbols_by_reference[reference]
                    for reference in references
                    if reference in symbols_by_reference
                },
                key=lambda item: (item.casefold(), item),
            )
        )
        if len({symbol.casefold() for symbol in symbols}) < 2:
            continue
        peers.append(ConnectorNamedPowerAliasPeer(group, function, symbols))

    return tuple(
        sorted(
            peers,
            key=lambda item: (
                item.group.part_id.casefold(),
                item.group.pin_number.casefold(),
                item.function.casefold(),
            ),
        )
    )


def connector_named_power_alias_evidence(
    peer: ConnectorNamedPowerAliasPeer,
) -> dict[str, tuple[str, ...]]:
    """Build stable evidence shared by named connector power-pin rules."""
    group = peer.group
    evidence: dict[str, tuple[str, ...]] = {
        **group.assignments,
        "peer_identity_basis": ("part_id",),
        "peer_identity": (group.part_id,),
        "peer_symbols": peer.symbols,
        "pin_number": (group.pin_number,),
        "pin_function": (peer.function,),
        "pin_electrical_type": (group.pin_electrical_type,),
    }
    if group.peer_assignment_group is not None:
        evidence["peer_assignment_group"] = (group.peer_assignment_group,)
        evidence["peer_assignment_basis"] = group.peer_assignment_basis
    return evidence
