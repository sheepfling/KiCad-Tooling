"""Review likely USB-C connectors missing a project-authored port-role map."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .connector_identity import connector_candidate_references
from .models import NetlistContract, UsbCAnalysis

UsbCPortRosterState = Literal["not_configured", "pending", "not_applicable", "required"]


@dataclass(frozen=True)
class UsbCPortRosterContext:
    """Project USB-C port coverage and its source binding for one lint run."""

    state: UsbCPortRosterState
    analysis: UsbCAnalysis | None = None
    source_path: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class UnmappedUsbCPort:
    """Connector candidate with paired CC pin functions absent from the role map."""

    reference: str
    cc1_pins: tuple[str, ...]
    cc2_pins: tuple[str, ...]
    signal_assignments: tuple[str, ...]


def _mapped_references(analysis: UsbCAnalysis | None) -> set[str]:
    if analysis is None:
        return set()
    return {port.connector.casefold() for port in analysis.ports}


def _pin_assignments(observed: NetlistContract) -> dict[str, set[str]]:
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)
    for net, pins in observed.unconnected_nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(f"unassigned ({net})")
    return assignments


def unmapped_usb_c_ports(
    observed: NetlistContract,
    roster: UsbCPortRosterContext,
    declared_connector_references: tuple[str, ...] = (),
) -> tuple[UnmappedUsbCPort, ...]:
    """Prompt for role review on connectors exporting both CC1 and CC2 pin functions.

    Exact pin functions, bounded native connector identity, and project-reviewed
    connector references are candidate evidence only. This check does not infer
    source, sink, dual-role, resistor, controller, protection, VBUS, or grounding
    requirements.
    """
    components = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    mapped = _mapped_references(roster.analysis)
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_connector_references)
    }
    assignments = _pin_assignments(observed)
    pins_by_reference: dict[str, dict[str, list[str]]] = {}

    for pin, function in observed.pin_functions.items():
        reference, separator, _number = pin.rpartition(".")
        if not separator:
            continue
        canonical_reference = components.get(reference.casefold())
        if (
            canonical_reference is None
            or canonical_reference.casefold() not in connector_references
        ):
            continue
        key = canonical_reference.casefold()
        if key in dnp or key in mapped:
            continue
        normalized_function = re.sub(r"[^a-z0-9]", "", function.casefold())
        if normalized_function not in {"cc1", "cc2"}:
            continue
        pins_by_reference.setdefault(key, {}).setdefault(normalized_function, []).append(pin)

    candidates: list[UnmappedUsbCPort] = []
    for reference_key, functions in sorted(pins_by_reference.items()):
        cc1 = tuple(sorted(functions.get("cc1", ()), key=str.casefold))
        cc2 = tuple(sorted(functions.get("cc2", ()), key=str.casefold))
        if not cc1 or not cc2:
            continue
        reference = components[reference_key]
        connector_pins = (*cc1, *cc2)
        signal_assignments = tuple(
            sorted(
                (
                    f"{pin}={','.join(sorted(assignments.get(pin.casefold(), ()))) or 'no net'}"
                    for pin in connector_pins
                ),
                key=str.casefold,
            )
        )
        candidates.append(
            UnmappedUsbCPort(
                reference=reference,
                cc1_pins=cc1,
                cc2_pins=cc2,
                signal_assignments=signal_assignments,
            )
        )

    return tuple(candidates)
