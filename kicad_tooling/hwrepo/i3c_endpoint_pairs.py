"""Recognize source-bound I3C SDA/SCL endpoint pairs."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .bus_signal_roles import i3c_signal_identity
from .casefold_mapping_lookup import casefolded_unique_index
from .connector_pin_metadata import connector_pin_metadata_matches_inventory
from .netlist_contract_models import NetlistContract

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class I3cEndpointPair:
    """One fitted U/IC with one uniquely assigned native I3C channel pair."""

    reference: str
    sda_pin: str
    sda_net: str
    scl_pin: str
    scl_net: str
    channel: str | None = None


def i3c_endpoint_pairs(observed: NetlistContract) -> tuple[I3cEndpointPair, ...]:
    """Return complete, fitted I3C SDA/SCL pin pairs on distinct exact nets."""
    symbols = casefolded_unique_index(observed.component_symbols)
    references = casefolded_unique_index(
        {reference: reference for reference in observed.component_symbols}
    )
    components = casefolded_unique_index(observed.components)
    inventories = casefolded_unique_index(observed.component_pin_numbers)
    functions = casefolded_unique_index(observed.pin_functions)
    electrical_types = casefolded_unique_index(observed.pin_electrical_types)
    assignments: dict[str, set[str]] = defaultdict(set)
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments[pin.casefold()].add(net)
    dnp = {reference.casefold() for reference in observed.dnp_components}

    endpoints: list[I3cEndpointPair] = []
    for reference_key in sorted(symbols):
        reference = references.get(reference_key)
        if (
            reference is None
            or not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in components
        ):
            continue
        numbers = inventories.get(reference_key)
        if (
            numbers is None
            or len({number.casefold() for number in numbers}) != len(numbers)
            or not connector_pin_metadata_matches_inventory(
                reference_key, numbers, functions, electrical_types
            )
        ):
            continue

        by_channel: dict[str | None, dict[str, list[str]]] = defaultdict(
            lambda: {"SDA": [], "SCL": []}
        )
        for number in numbers:
            pin = f"{reference}.{number}"
            identity = i3c_signal_identity(functions[f"{reference_key}.{number.casefold()}"])
            if identity is not None:
                by_channel[identity.channel][identity.role].append(pin)

        for channel in sorted(by_channel, key=lambda item: (item is not None, item or "")):
            roles = by_channel[channel]
            if len(roles["SDA"]) != 1 or len(roles["SCL"]) != 1:
                continue
            sda_pin, scl_pin = roles["SDA"][0], roles["SCL"][0]
            sda_nets = assignments.get(sda_pin.casefold(), set())
            scl_nets = assignments.get(scl_pin.casefold(), set())
            if len(sda_nets) != 1 or len(scl_nets) != 1:
                continue
            sda_net, scl_net = next(iter(sda_nets)), next(iter(scl_nets))
            if sda_net.casefold() == scl_net.casefold():
                continue
            endpoints.append(
                I3cEndpointPair(reference, sda_pin, sda_net, scl_pin, scl_net, channel)
            )

    return tuple(
        sorted(
            endpoints,
            key=lambda item: (
                item.reference.casefold(),
                item.reference,
                item.channel is not None,
                item.channel or "",
                item.sda_pin.casefold(),
                item.sda_pin,
                item.scl_pin.casefold(),
                item.scl_pin,
            ),
        )
    )
