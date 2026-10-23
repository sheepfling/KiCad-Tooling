"""Review fitted SPI clock/control and data roles assigned to one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_participants import is_spi_ic_reference, spi_signal_role_and_channel

RULE_ID = "bus.spi_clock_control_data_same_net"
_SPI_CONTROL_ROLES = {"clock", "chip_select"}
_SPI_DATA_ROLES = {"data_input", "data_output"}
_ROLE_ORDER = {"clock": 0, "chip_select": 1, "data_input": 2, "data_output": 3}


def spi_clock_control_data_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find one supported SPI clock/control and data pin pair on the same net.

    This opt-in review clue does not prove that a device uses the function names
    as its configured SPI roles. Data-input/output pairs are owned by the more
    specific SPI data-role same-net rule.
    """
    fitted = {
        reference.casefold(): reference
        for reference in observed.components
        if is_spi_ic_reference(reference)
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }

    role_pins: dict[tuple[str, str, str], list[tuple[str, str, tuple[str, ...], str]]] = {}
    invalid_inventory: set[tuple[str, str, str]] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted or reference_key in dnp:
            continue
        role_channel = spi_signal_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        key = (reference_key, channel, role)
        if number.casefold() not in pin_numbers.get(reference_key, set()):
            invalid_inventory.add(key)
        assignments = tuple(
            sorted(nets_by_pin.get(pin.casefold(), ()), key=lambda item: (item.casefold(), item))
        )
        role_pins.setdefault(key, []).append(
            (pin, function, assignments, pin_types.get(pin.casefold(), "unknown"))
        )

    by_reference_channel: dict[
        tuple[str, str], dict[str, list[tuple[str, str, tuple[str, ...], str]]]
    ] = {}
    for (reference, channel, role), endpoints in role_pins.items():
        by_reference_channel.setdefault((reference, channel), {})[role] = endpoints

    findings: list[Candidate] = []
    for (reference_key, channel), roles in sorted(by_reference_channel.items()):
        control_roles = sorted(_SPI_CONTROL_ROLES & roles.keys(), key=_ROLE_ORDER.__getitem__)
        data_roles = sorted(_SPI_DATA_ROLES & roles.keys(), key=_ROLE_ORDER.__getitem__)
        for control_role in control_roles:
            for data_role in data_roles:
                control_key = (reference_key, channel, control_role)
                data_key = (reference_key, channel, data_role)
                if control_key in invalid_inventory or data_key in invalid_inventory:
                    continue
                controls = roles[control_role]
                data_endpoints = roles[data_role]
                if len(controls) != 1 or len(data_endpoints) != 1:
                    continue
                control, data = controls[0], data_endpoints[0]
                control_pin, control_function, control_nets, control_type = control
                data_pin, data_function, data_nets, data_type = data
                if len(control_nets) != 1 or len(data_nets) != 1:
                    continue
                if control_nets[0] != data_nets[0]:
                    continue
                if control_type == data_type == "output":
                    continue

                reference = fitted[reference_key]
                net = control_nets[0]
                channel_label = (
                    "SPI"
                    if channel == "default"
                    else f"SPI channel {channel.removeprefix('index')}"
                )
                findings.append(
                    Candidate(
                        rule_id=RULE_ID,
                        subject=(
                            f"{reference}: {channel_label} {control_role.replace('_', ' ')} "
                            f"{control_function} and {data_role.replace('_', ' ')} "
                            f"{data_function} share {net}"
                        ),
                        message=(
                            f"Fitted IC {reference} has a native SPI {control_role.replace('_', ' ')} "
                            f"pin {control_pin} ({control_function}, {control_type}) and a "
                            f"{data_role.replace('_', ' ')} pin {data_pin} "
                            f"({data_function}, {data_type}) on one schematic net ({net}). "
                            "Review whether the assignment is intentional. Pin-function names "
                            "do not establish the device's configured mode or required topology."
                        ),
                        evidence={
                            "component": (reference,),
                            "channel": (channel_label,),
                            "spi_role_pin": (control_pin,),
                            "spi_role": (control_role,),
                            "spi_function": (control_function,),
                            "spi_electrical_type": (control_type,),
                            "data_pin": (data_pin,),
                            "data_role": (data_role,),
                            "data_function": (data_function,),
                            "data_electrical_type": (data_type,),
                            "net": (net,),
                        },
                    )
                )
    return tuple(findings)
