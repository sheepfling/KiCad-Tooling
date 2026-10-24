"""Review unassigned I2C pins only when their local pair is partly connected."""

from __future__ import annotations

from dataclasses import dataclass

from .bus_signal_roles import i2c_signal_role
from .models import NetlistContract


@dataclass(frozen=True)
class UnconnectedI2cSignalPin:
    pin: str
    function: str
    role: str
    paired_pin: str
    paired_net: str


def unconnected_i2c_signal_pins(
    observed: NetlistContract,
) -> tuple[UnconnectedI2cSignalPin, ...]:
    """Find an open SDA/SCL function beside exactly one assigned pair member.

    A component with several pins sharing an SDA or SCL alias is ambiguous and
    is skipped. The function aliases do not establish that the interface is
    required, and an entirely open pair is not evidence that it is used.
    """
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    component_references = {reference.casefold() for reference in observed.components}
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    component_pin_numbers = {
        reference.casefold(): {number.casefold() for number in pin_numbers}
        for reference, pin_numbers in observed.component_pin_numbers.items()
    }
    groups: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or reference_key not in component_references
            or reference_key in dnp_references
            or number.casefold() not in component_pin_numbers.get(reference_key, set())
        ):
            continue
        role = i2c_signal_role(function)
        if role is not None:
            groups.setdefault(reference_key, {}).setdefault(role, []).append((pin, function))

    found: list[UnconnectedI2cSignalPin] = []
    for roles in groups.values():
        sda_pins = roles.get("SDA", [])
        scl_pins = roles.get("SCL", [])
        if len(sda_pins) != 1 or len(scl_pins) != 1:
            continue
        (sda_pin, sda_function), (scl_pin, scl_function) = sda_pins[0], scl_pins[0]
        sda_nets = assignments.get(sda_pin.casefold(), set())
        scl_nets = assignments.get(scl_pin.casefold(), set())
        if not sda_nets and len(scl_nets) == 1:
            found.append(
                UnconnectedI2cSignalPin(
                    pin=sda_pin,
                    function=sda_function,
                    role="SDA",
                    paired_pin=scl_pin,
                    paired_net=next(iter(scl_nets)),
                )
            )
        elif not scl_nets and len(sda_nets) == 1:
            found.append(
                UnconnectedI2cSignalPin(
                    pin=scl_pin,
                    function=scl_function,
                    role="SCL",
                    paired_pin=sda_pin,
                    paired_net=next(iter(sda_nets)),
                )
            )
    return tuple(sorted(found, key=lambda item: (item.pin.casefold(), item.role)))
