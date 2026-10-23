"""Review RS-485 transceiver data pins against explicit UART net labels."""

from __future__ import annotations

import re
from typing import Literal

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_participants import serial_function_role_and_channel

RULE_ID = "bus.rs485_data_direction_label_mismatch"
_DATA_PIN_ROLES: dict[str, Literal["tx", "rx"]] = {
    "d": "tx",
    "di": "tx",
    "driverdatain": "tx",
    "driverinput": "tx",
    "r": "rx",
    "ro": "rx",
    "receiverdataout": "rx",
    "receiveroutput": "rx",
}


def rs485_data_pin_role(function: str) -> Literal["tx", "rx"] | None:
    """Recognize a narrow RS-485 driver-input or receiver-output function."""
    compact = re.sub(r"[^a-z0-9]", "", function.casefold())
    return _DATA_PIN_ROLES.get(compact)


def rs485_data_direction_label_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review paired transceiver D/R pins assigned to opposite UART directions.

    A transceiver driver-data input corresponds to host TX, and its
    receiver-data output corresponds to host RX. Both native pins and labels
    must be present on one fitted IC, with explicit UART/USART labels on the
    same channel. This is a review clue, not an authored pin-map requirement.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    pins_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        role = rs485_data_pin_role(function)
        if not separator or not number or role is None:
            continue
        pins_by_reference.setdefault(reference.casefold(), {}).setdefault(role, []).append(
            (pin, number)
        )

    references = {reference.casefold(): reference for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for folded_reference, roles in sorted(pins_by_reference.items()):
        reference = references.get(folded_reference)
        if (
            reference is None
            or folded_reference in dnp_references
            or not is_integrated_circuit_reference(reference)
            or len(roles.get("tx", ())) != 1
            or len(roles.get("rx", ())) != 1
        ):
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None:
            continue
        known_numbers = {item.casefold() for item in inventory}
        data_pins = {role: roles[role][0] for role in ("tx", "rx")}
        if any(number.casefold() not in known_numbers for _pin, number in data_pins.values()):
            continue

        assignments: dict[str, tuple[str, str]] = {}
        for role, (pin, _number) in data_pins.items():
            assigned_nets = nets_by_pin.get(pin.casefold(), set())
            if len(assigned_nets) != 1:
                break
            net = next(iter(assigned_nets))
            net_role = serial_function_role_and_channel(net)
            if net_role is None or not net_role[1].startswith(("uart", "usart")):
                break
            assignments[role] = (net, net_role[1])
        if set(assignments) != {"tx", "rx"}:
            continue
        if assignments["tx"][1] != assignments["rx"][1]:
            continue

        for pin_role in ("tx", "rx"):
            pin, _number = data_pins[pin_role]
            net, channel = assignments[pin_role]
            net_role = serial_function_role_and_channel(net)
            if net_role is None or net_role[0] == pin_role:
                continue
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=f"{pin}: {observed.pin_functions[pin]} on {net}",
                    message=(
                        f"The RS-485 data-pin function indicates host {pin_role.upper()}, but "
                        f"the assigned net name {net!r} indicates host {net_role[0].upper()}. "
                        "Review the transceiver pin map and naming convention; the heuristic "
                        "does not establish a required connection."
                    ),
                    evidence={
                        "reference": (reference,),
                        "pin": (pin,),
                        "pin_function": (observed.pin_functions[pin],),
                        "pin_role": (pin_role,),
                        "channel": (channel,),
                        "net": (net,),
                        "net_role": (net_role[0],),
                    },
                )
            )
    return tuple(findings)
