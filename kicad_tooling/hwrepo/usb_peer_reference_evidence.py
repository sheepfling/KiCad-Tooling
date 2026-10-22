"""Collect exact schematic observations for USB endpoint reference-net reviews."""

from __future__ import annotations

from .models import NetlistContract
from .usb_peer_endpoint_analysis import casefold_mapping
from .usb_peer_reference_types import (
    UsbPeerReferenceComponentObservation,
    UsbPeerReferenceComponentPin,
)


def usb_reference_net_component_observations(
    observed: NetlistContract,
    connector_reference: str,
    phy_reference: str,
    connector_reference_net: str,
    phy_reference_net: str,
) -> tuple[UsbPeerReferenceComponentObservation, ...]:
    """List non-endpoint components with uniquely assigned pins on both reference nets.

    This captures normalized schematic net membership only. It does not infer
    component conduction, fitted state, intended bonding, or PCB continuity.
    """
    endpoint_references = {connector_reference.casefold(), phy_reference.casefold()}
    net_roles = {
        connector_reference_net.casefold(): 0,
        phy_reference_net.casefold(): 1,
    }
    if len(net_roles) != 2:
        return ()

    pin_net_assignments: dict[str, set[tuple[str, str]]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_net_assignments.setdefault(pin.casefold(), set()).add((net.casefold(), net))

    component_pins: dict[str, dict[int, set[tuple[str, str]]]] = {}
    component_names: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        role = net_roles.get(net.casefold())
        if role is None:
            continue
        for pin in pins:
            reference, separator, _number = pin.rpartition(".")
            if not separator or reference.casefold() in endpoint_references:
                continue
            if pin_net_assignments.get(pin.casefold()) != {(net.casefold(), net)}:
                continue
            reference_key = reference.casefold()
            component_names.setdefault(reference_key, set()).add(reference)
            component_pins.setdefault(reference_key, {}).setdefault(role, set()).add((pin, net))

    components = casefold_mapping(observed.components)
    symbols = casefold_mapping(observed.component_symbols)
    functions = casefold_mapping(observed.pin_functions)
    electrical_types = casefold_mapping(observed.pin_electrical_types)
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    observations: list[UsbPeerReferenceComponentObservation] = []
    for reference_key in sorted(component_pins):
        pins_by_role = component_pins[reference_key]
        if 0 not in pins_by_role or 1 not in pins_by_role:
            continue
        reference_names = component_names[reference_key]
        if len(reference_names) != 1:
            continue
        reference = next(iter(reference_names))
        assignments = tuple(
            UsbPeerReferenceComponentPin(
                pin=pin,
                net=net,
                function=functions.get(pin.casefold()),
                electrical_type=electrical_types.get(pin.casefold()),
            )
            for role in (0, 1)
            for pin, net in sorted(
                pins_by_role[role],
                key=lambda item: (item[0].casefold(), item[0], item[1].casefold(), item[1]),
            )
        )
        component = components.get(reference_key)
        observations.append(
            UsbPeerReferenceComponentObservation(
                reference=reference,
                symbol=symbols.get(reference_key),
                value=None if component is None else component.value,
                footprint=None if component is None else component.footprint,
                dnp_metadata_listed=reference_key in dnp_references,
                pin_assignments=assignments,
            )
        )
    return tuple(
        sorted(
            observations,
            key=lambda item: (item.reference.casefold(), item.reference),
        )
    )
