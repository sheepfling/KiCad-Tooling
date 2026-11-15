"""Native pin evidence shared by connector peer-function review rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .connector_footprint_peer_groups import (
    ConnectorFootprintPeerGroup,
    complete_connector_footprint_peer_pin_inventory,
)
from .connector_identity import native_pin_metadata_is_missing
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


@dataclass(frozen=True, slots=True)
class ConnectorFootprintPeerPinFunctionObservation:
    """One peer's native pin function, electrical type, assignment, and symbol."""

    reference: str
    pin: str
    function: str
    electrical_type: str
    nets: tuple[str, ...]
    symbol: str


PeerPinFunctionRows: TypeAlias = tuple[
    tuple[str, tuple[ConnectorFootprintPeerPinFunctionObservation, ...]], ...
]


def connector_footprint_peer_pin_function_rows(
    observed: NetlistContract,
    group: ConnectorFootprintPeerGroup,
    *,
    allow_missing_functions: bool = False,
) -> PeerPinFunctionRows | None:
    """Collect ordered native pin evidence, optionally retaining absent names."""
    inventory = complete_connector_footprint_peer_pin_inventory(observed, group.references)
    if inventory is None:
        return None
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): value for pin, value in observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): value for reference, value in observed.component_symbols.items()
    }
    pin_nets = netlist_pin_net_index(observed)
    rows: list[tuple[str, tuple[ConnectorFootprintPeerPinFunctionObservation, ...]]] = []
    for pin_number in inventory.pin_numbers:
        peer_rows: list[ConnectorFootprintPeerPinFunctionObservation] = []
        for reference in group.references:
            pin = f"{reference}.{inventory.displayed_numbers_by_reference[reference.casefold()][pin_number.casefold()]}"
            function = functions.get(pin.casefold())
            electrical_type = electrical_types.get(pin.casefold())
            symbol = symbols.get(reference.casefold())
            if (
                (native_pin_metadata_is_missing(function) and not allow_missing_functions)
                or native_pin_metadata_is_missing(electrical_type)
                or symbol is None
            ):
                return None
            assert electrical_type is not None
            peer_rows.append(
                ConnectorFootprintPeerPinFunctionObservation(
                    reference=reference,
                    pin=pin,
                    function="" if function is None else str(function),
                    electrical_type=str(electrical_type),
                    nets=tuple(
                        sorted(
                            pin_nets.get(pin.casefold(), ()),
                            key=lambda net: (net.casefold(), net),
                        )
                    ),
                    symbol=symbol,
                )
            )
        rows.append((pin_number, tuple(peer_rows)))
    return tuple(rows)


def peer_pin_rows_share_one_common_assignment(
    rows: tuple[ConnectorFootprintPeerPinFunctionObservation, ...],
) -> bool:
    """Require one identical nonempty native net assignment for every peer pin."""
    return (
        bool(rows)
        and all(len(item.nets) == 1 and item.nets[0].strip() for item in rows)
        and len({item.nets[0] for item in rows}) == 1
    )
