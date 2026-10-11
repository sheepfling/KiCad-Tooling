"""Find fitted CAN peers on one native line pair with split references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .bus_signal_roles import can_function_role
from .models import NetlistContract
from .peer_reference_assignments import (
    PeerReferencePinAssignment,
    peer_reference_assignments,
)

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True)
class CanPeerReferenceEndpoint:
    """One fitted transceiver with unique native CANH/CANL assignments."""

    reference: str
    canh_pin: str
    canh_net: str
    canl_pin: str
    canl_net: str
    reference_net: str | None
    reference_pins: tuple[PeerReferencePinAssignment, ...]


@dataclass(frozen=True)
class CanPeerReferenceBus:
    """Coverage for fitted endpoints sharing one exact native CAN line pair."""

    canh_net: str
    canl_net: str
    endpoints: tuple[CanPeerReferenceEndpoint, ...]
    incomplete_references: tuple[str, ...]
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
    ]


@dataclass(frozen=True)
class CanPeerReferenceScan:
    """Recognized direct CAN endpoints and source-bound reference states."""

    recognized_endpoint_count: int
    buses: tuple[CanPeerReferenceBus, ...]

    @property
    def reviews(self) -> tuple[CanPeerReferenceBus, ...]:
        return tuple(
            bus
            for bus in self.buses
            if bus.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        )


def scan_can_peer_references(observed: NetlistContract) -> CanPeerReferenceScan:
    """Group complete fitted CANH/CANL pairs and inspect explicit return pins.

    The scan uses only native pin functions and exact assigned CANH/CANL nets.
    It does not identify CAN membership by reference/value naming, infer that
    references should be common, or resolve isolated/translated segments.
    """
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    pin_functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}
    pin_numbers = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    component_references = {
        reference.casefold(): reference for reference in observed.components
    }
    symbol_references = {reference.casefold() for reference in observed.component_symbols}
    dnp = {reference.casefold() for reference in observed.dnp_components}

    endpoints: list[CanPeerReferenceEndpoint] = []
    for reference_key, reference in sorted(
        component_references.items(), key=lambda item: (item[0], item[1])
    ):
        if (
            not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in symbol_references
        ):
            continue
        known_numbers = {number.casefold() for number in pin_numbers.get(reference_key, ())}
        role_pins: dict[str, list[tuple[str, str]]] = {"CANH": [], "CANL": []}
        for pin_key, function in pin_functions.items():
            pin_reference, separator, number = pin_key.rpartition(".")
            if not separator or pin_reference != reference_key or number not in known_numbers:
                continue
            role = can_function_role(function)
            if role is None:
                continue
            assigned_nets = pin_nets.get(pin_key, set())
            if len(assigned_nets) == 1:
                role_pins[role].append((f"{reference}.{number}", next(iter(assigned_nets))))
        if len(role_pins["CANH"]) != 1 or len(role_pins["CANL"]) != 1:
            continue
        canh_pin, canh_net = role_pins["CANH"][0]
        canl_pin, canl_net = role_pins["CANL"][0]
        if canh_net.casefold() == canl_net.casefold():
            continue
        reference_evidence = peer_reference_assignments(
            reference,
            observed,
            pin_nets,
            pin_numbers.get(reference_key, ()),
        )
        endpoints.append(
            CanPeerReferenceEndpoint(
                reference=reference,
                canh_pin=canh_pin,
                canh_net=canh_net,
                canl_pin=canl_pin,
                canl_net=canl_net,
                reference_net=reference_evidence.net,
                reference_pins=reference_evidence.pins,
            )
        )

    grouped: dict[tuple[str, str], list[CanPeerReferenceEndpoint]] = {}
    for endpoint in endpoints:
        grouped.setdefault(
            (endpoint.canh_net.casefold(), endpoint.canl_net.casefold()), []
        ).append(endpoint)

    buses: list[CanPeerReferenceBus] = []
    for endpoints_on_bus in grouped.values():
        if len(endpoints_on_bus) < 2:
            continue
        ordered = tuple(
            sorted(endpoints_on_bus, key=lambda item: (item.reference.casefold(), item.reference))
        )
        reference_nets = {
            item.reference_net.casefold()
            for item in ordered
            if item.reference_net is not None
        }
        incomplete = tuple(item.reference for item in ordered if item.reference_net is None)
        if len(reference_nets) > 1:
            disposition = (
                "PARTIAL_SPLIT_REFERENCE_REVIEW" if incomplete else "SPLIT_REFERENCE_REVIEW"
            )
        elif incomplete:
            disposition = "INCOMPLETE"
        else:
            disposition = "COMMON_REFERENCE"
        buses.append(
            CanPeerReferenceBus(
                canh_net=ordered[0].canh_net,
                canl_net=ordered[0].canl_net,
                endpoints=ordered,
                incomplete_references=incomplete,
                disposition=disposition,
            )
        )
    return CanPeerReferenceScan(
        recognized_endpoint_count=len(endpoints),
        buses=tuple(
            sorted(
                buses,
                key=lambda item: (item.canh_net.casefold(), item.canl_net.casefold()),
            )
        ),
    )
