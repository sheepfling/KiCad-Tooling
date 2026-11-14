"""Bounded USB 2.0 data-pair endpoints shared by interface checks."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_pairs import usb_data_function_identity
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index
from .usb_peer_endpoint_analysis import IC_REFERENCE


@dataclass(frozen=True, slots=True)
class UsbDataPairEndpoint:
    """One uniquely recognized fitted IC D+/D- pair and native net assignment."""

    reference: str
    port_group: str | None
    positive_pin: str
    negative_pin: str
    positive_net: str
    negative_net: str
    positive_type: str
    negative_type: str


def usb_data_pair_endpoints(observed: NetlistContract) -> tuple[UsbDataPairEndpoint, ...]:
    """Return complete, unique USB-like IC data pairs with one net per pin.

    Function names provide a bounded recognition clue only. DNP components,
    duplicate roles, missing inventory, and open or ambiguous pin assignments
    are omitted so downstream checks share the same evidence boundary.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if IC_REFERENCE.fullmatch(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin = netlist_pin_net_index(observed)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    roles_by_reference: dict[
        str, dict[tuple[str | None, str], list[tuple[str, tuple[str, ...]]]]
    ] = {}
    invalid_inventory_references: set[str] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted:
            continue
        identity = usb_data_function_identity(function)
        if identity is None:
            continue
        port_group, side = identity
        inventory = pin_numbers.get(reference_key, set())
        if not inventory or number.casefold() not in inventory:
            invalid_inventory_references.add(reference_key)
            continue
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        roles_by_reference.setdefault(reference_key, {}).setdefault((port_group, side), []).append(
            (f"{fitted[reference_key]}.{number}", assignments)
        )

    endpoints: list[UsbDataPairEndpoint] = []
    for reference_key, roles in sorted(roles_by_reference.items()):
        if reference_key in dnp or reference_key in invalid_inventory_references:
            continue
        port_groups = sorted(
            {port_group for port_group, _ in roles},
            key=lambda item: (item is not None, item or ""),
        )
        for port_group in port_groups:
            positive_pins = roles.get((port_group, "positive"), ())
            negative_pins = roles.get((port_group, "negative"), ())
            if len(positive_pins) != 1 or len(negative_pins) != 1:
                continue
            positive_pin, positive_assignments = positive_pins[0]
            negative_pin, negative_assignments = negative_pins[0]
            if len(positive_assignments) != 1 or len(negative_assignments) != 1:
                continue
            endpoints.append(
                UsbDataPairEndpoint(
                    reference=fitted[reference_key],
                    port_group=port_group,
                    positive_pin=positive_pin,
                    negative_pin=negative_pin,
                    positive_net=positive_assignments[0],
                    negative_net=negative_assignments[0],
                    positive_type=pin_types.get(positive_pin.casefold(), "unknown"),
                    negative_type=pin_types.get(negative_pin.casefold(), "unknown"),
                )
            )
    return tuple(
        sorted(
            endpoints,
            key=lambda item: (
                item.reference.casefold(),
                item.reference,
                item.port_group is not None,
                item.port_group or "",
                item.positive_pin.casefold(),
                item.positive_pin,
            ),
        )
    )
