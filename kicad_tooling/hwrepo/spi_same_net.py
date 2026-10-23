"""Review one fitted SPI IC's data-input and data-output pins on one net."""

from __future__ import annotations

from .design_lint_types import Candidate
from .models import NetlistContract
from .spi_participants import is_spi_ic_reference, spi_data_function_role_and_channel

RULE_ID = "bus.spi_data_input_output_same_net"


def spi_data_input_output_same_net_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Find one uniquely assigned SPI data-input/output pair on the same native net.

    This is a review clue: loopback, single-wire, and part-specific modes can
    intentionally join the pins. Open or duplicate role pins, missing pin
    inventory, DNP parts, and ambiguous assignments are left unclassified.
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

    roles: dict[tuple[str, str, str], list[tuple[str, str, tuple[str, ...], str]]] = {}
    invalid_inventory: set[tuple[str, str, str]] = set()
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if not separator or reference_key not in fitted or reference_key in dnp:
            continue
        role_channel = spi_data_function_role_and_channel(function)
        if role_channel is None:
            continue
        role, channel = role_channel
        key = (reference_key, channel, role)
        if number.casefold() not in pin_numbers.get(reference_key, set()):
            invalid_inventory.add(key)
        assignment = tuple(sorted(nets_by_pin.get(pin.casefold(), ()), key=str.casefold))
        roles.setdefault(key, []).append(
            (pin, function, assignment, pin_types.get(pin.casefold(), "unknown"))
        )

    by_reference_channel: dict[
        tuple[str, str], dict[str, list[tuple[str, str, tuple[str, ...], str]]]
    ] = {}
    for (reference, channel, role), endpoints in roles.items():
        by_reference_channel.setdefault((reference, channel), {})[role] = endpoints

    findings: list[Candidate] = []
    for (reference_key, channel), role_endpoints in sorted(by_reference_channel.items()):
        inputs = role_endpoints.get("input", [])
        outputs = role_endpoints.get("output", [])
        if len(inputs) != 1 or len(outputs) != 1:
            continue
        input_endpoint, output_endpoint = inputs[0], outputs[0]
        input_key = (reference_key, channel, "input")
        output_key = (reference_key, channel, "output")
        if input_key in invalid_inventory or output_key in invalid_inventory:
            continue
        input_pin, input_function, input_nets, input_type = input_endpoint
        output_pin, output_function, output_nets, output_type = output_endpoint
        if len(input_nets) != 1 or len(output_nets) != 1:
            continue
        if input_nets[0].casefold() != output_nets[0].casefold():
            continue
        if input_type == output_type == "output":
            continue

        reference = fitted[reference_key]
        net = input_nets[0]
        channel_label = (
            "SPI" if channel == "default" else f"SPI channel {channel.removeprefix('index')}"
        )
        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{reference}: {channel_label} data-role pins share {net}",
                message=(
                    f"Fitted IC {reference} has controller-to-peripheral SPI data-role pin "
                    f"{input_pin} ({input_function}) and peripheral-to-controller data-role pin "
                    f"{output_pin} ({output_function}) on one schematic net ({net}); native pin "
                    f"types are {input_type} and {output_type}. Review whether this is intentional "
                    "loopback, single-wire operation, or a pin-assignment mistake. Function names "
                    "do not establish this IC's configured direction or the intended topology."
                ),
                evidence={
                    "component": (reference,),
                    "channel": (channel_label,),
                    "controller_to_peripheral_pin": (input_pin,),
                    "controller_to_peripheral_function": (input_function,),
                    "controller_to_peripheral_type": (input_type,),
                    "peripheral_to_controller_pin": (output_pin,),
                    "peripheral_to_controller_function": (output_function,),
                    "peripheral_to_controller_type": (output_type,),
                    "net": (net,),
                },
            )
        )
    return tuple(findings)
