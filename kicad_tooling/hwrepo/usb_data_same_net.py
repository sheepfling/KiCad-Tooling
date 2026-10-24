"""Review fitted USB 2.0 PHY data pins assigned to one schematic net."""

from __future__ import annotations

from .bus_signal_pairs import usb_data_function_identity
from .design_lint_types import Candidate
from .models import NetlistContract
from .usb_peer_endpoint_analysis import IC_REFERENCE

RULE_ID = "bus.usb_dp_dm_same_net"


def usb_data_same_net_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Find one explicit USB 2.0 D+/D- pin pair on the same exact net.

    Function labels are only a bounded recognition clue. The check requires
    both pins to be in the native inventory and uniquely assigned, and leaves
    two output pins to native ERC.
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
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)
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

    findings: list[Candidate] = []
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
            net = positive_assignments[0]
            negative_net = negative_assignments[0]
            if net.casefold() != negative_net.casefold() or net != negative_net:
                continue
            if (
                pin_types.get(positive_pin.casefold())
                == pin_types.get(negative_pin.casefold())
                == "output"
            ):
                continue

            reference = fitted[reference_key]
            port_label = "unindexed" if port_group is None else port_group
            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(f"{reference}: USB data port {port_label} D+/D- pins share {net}"),
                    message=(
                        f"The explicit USB 2.0 D+ pin {positive_pin} and D- pin {negative_pin} "
                        f"on {reference} share one schematic net ({net}). Review whether this "
                        "is intentional. Function names are clues only; this check does not "
                        "prove the part implements USB or establish the intended topology."
                    ),
                    evidence={
                        "component": (reference,),
                        "USB_port_group": (port_label,),
                        "D+_pin": (positive_pin,),
                        "D-_pin": (negative_pin,),
                        "D+_electrical_type": (pin_types.get(positive_pin.casefold(), "unknown"),),
                        "D-_electrical_type": (pin_types.get(negative_pin.casefold(), "unknown"),),
                        "net": (net,),
                    },
                )
            )

    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
