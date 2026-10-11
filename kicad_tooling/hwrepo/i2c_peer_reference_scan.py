"""Find shared I2C nets whose fitted IC peers expose separate references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .i2c_addressing import i2c_signal_role
from .models import NetlistContract
from .peer_reference_assignments import (
    PeerReferencePinAssignment as I2cReferencePinAssignment,
)
from .peer_reference_assignments import (
    peer_reference_assignments,
)

_IC_REFERENCE = re.compile(r"^(?:U|IC)[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True)
class I2cPeerEndpoint:
    """One fitted IC with one unambiguous native SDA/SCL pair."""

    reference: str
    sda_pin: str
    scl_pin: str
    sda_net: str
    scl_net: str
    reference_net: str | None
    reference_pins: tuple[I2cReferencePinAssignment, ...]


@dataclass(frozen=True)
class I2cPeerReferenceReview:
    """A shared native I2C bus with a split between explicit reference nets."""

    sda_net: str
    scl_net: str
    endpoints: tuple[I2cPeerEndpoint, ...]
    incomplete_references: tuple[str, ...]


@dataclass(frozen=True)
class I2cPeerReferenceBus:
    """Coverage for one exact shared I2C signal-net pair."""

    sda_net: str
    scl_net: str
    endpoints: tuple[I2cPeerEndpoint, ...]
    incomplete_references: tuple[str, ...]
    disposition: Literal[
        "COMMON_REFERENCE",
        "INCOMPLETE",
        "SPLIT_REFERENCE_REVIEW",
        "PARTIAL_SPLIT_REFERENCE_REVIEW",
    ]


@dataclass(frozen=True)
class I2cPeerReferenceScan:
    """Recognized single-port I2C endpoints and shared bus reference states."""

    recognized_endpoint_count: int
    buses: tuple[I2cPeerReferenceBus, ...]

    @property
    def reviews(self) -> tuple[I2cPeerReferenceReview, ...]:
        return tuple(
            I2cPeerReferenceReview(
                sda_net=bus.sda_net,
                scl_net=bus.scl_net,
                endpoints=bus.endpoints,
                incomplete_references=bus.incomplete_references,
            )
            for bus in self.buses
            if bus.disposition in {"SPLIT_REFERENCE_REVIEW", "PARTIAL_SPLIT_REFERENCE_REVIEW"}
        )


def scan_i2c_peer_references(
    observed: NetlistContract,
) -> I2cPeerReferenceScan:
    """Group fitted single-port I2C ICs by exact SDA/SCL nets and inspect references.

    Only native I2C pin functions, a complete native IC pin inventory, and
    explicitly assigned passive or power-input return pins participate. This
    scan does not infer compatibility from rail names or trace a translator.
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
    dnp = {reference.casefold() for reference in observed.dnp_components}
    endpoints: list[I2cPeerEndpoint] = []
    for reference in sorted(observed.components, key=lambda item: (item.casefold(), item)):
        reference_key = reference.casefold()
        if not _IC_REFERENCE.fullmatch(reference) or reference_key in dnp:
            continue
        known_numbers = {item.casefold() for item in pin_numbers.get(reference_key, ())}
        signal_pins: dict[str, list[tuple[str, str]]] = {"SDA": [], "SCL": []}
        for pin, function in pin_functions.items():
            pin_reference, separator, number = pin.rpartition(".")
            if not separator or pin_reference != reference_key or number not in known_numbers:
                continue
            role = i2c_signal_role(function)
            if role is None:
                continue
            assigned_nets = pin_nets.get(pin, set())
            if len(assigned_nets) == 1:
                signal_pins[role].append((f"{reference}.{number}", next(iter(assigned_nets))))
        if len(signal_pins["SDA"]) != 1 or len(signal_pins["SCL"]) != 1:
            continue
        sda_pin, sda_net = signal_pins["SDA"][0]
        scl_pin, scl_net = signal_pins["SCL"][0]
        if sda_net.casefold() == scl_net.casefold():
            continue
        reference_evidence = peer_reference_assignments(
            reference,
            observed,
            pin_nets,
            pin_numbers.get(reference_key, ()),
        )
        endpoints.append(
            I2cPeerEndpoint(
                reference=reference,
                sda_pin=sda_pin,
                scl_pin=scl_pin,
                sda_net=sda_net,
                scl_net=scl_net,
                reference_net=reference_evidence.net,
                reference_pins=reference_evidence.pins,
            )
        )

    grouped: dict[tuple[str, str], list[I2cPeerEndpoint]] = {}
    for endpoint in endpoints:
        grouped.setdefault((endpoint.sda_net.casefold(), endpoint.scl_net.casefold()), []).append(
            endpoint
        )

    buses: list[I2cPeerReferenceBus] = []
    for endpoints_for_bus in grouped.values():
        if len(endpoints_for_bus) < 2:
            continue
        reference_nets = {
            item.reference_net.casefold()
            for item in endpoints_for_bus
            if item.reference_net is not None
        }
        ordered = tuple(
            sorted(endpoints_for_bus, key=lambda item: (item.reference.casefold(), item.reference))
        )
        incomplete_references = tuple(
            item.reference for item in ordered if item.reference_net is None
        )
        disposition: Literal[
            "COMMON_REFERENCE",
            "INCOMPLETE",
            "SPLIT_REFERENCE_REVIEW",
            "PARTIAL_SPLIT_REFERENCE_REVIEW",
        ]
        if len(reference_nets) > 1:
            disposition = (
                "PARTIAL_SPLIT_REFERENCE_REVIEW"
                if incomplete_references
                else "SPLIT_REFERENCE_REVIEW"
            )
        elif incomplete_references:
            disposition = "INCOMPLETE"
        else:
            disposition = "COMMON_REFERENCE"
        buses.append(
            I2cPeerReferenceBus(
                sda_net=ordered[0].sda_net,
                scl_net=ordered[0].scl_net,
                endpoints=ordered,
                incomplete_references=incomplete_references,
                disposition=disposition,
            )
        )
    return I2cPeerReferenceScan(
        recognized_endpoint_count=len(endpoints),
        buses=tuple(
            sorted(buses, key=lambda item: (item.sda_net.casefold(), item.scl_net.casefold()))
        ),
    )


def scan_i2c_peer_reference_reviews(
    observed: NetlistContract,
) -> tuple[I2cPeerReferenceReview, ...]:
    """Return only shared buses with at least two known distinct references."""
    return scan_i2c_peer_references(observed).reviews
