"""Review serial TX/RX pin functions against explicit UART net labels."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .serial_participants import serial_function_role_and_channel

RULE_ID = "bus.serial_tx_rx_label_mismatch"


def serial_tx_rx_label_mismatch_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review fitted IC pins assigned to an explicitly opposite UART/USART label."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        functions_by_pin.setdefault(pin.casefold(), []).append((pin, function))

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for folded_pin, entries in sorted(functions_by_pin.items()):
        if len(entries) != 1:
            continue
        pin, function = entries[0]
        reference, separator, number = pin.rpartition(".")
        reference_key = reference.casefold()
        if (
            not separator
            or not is_integrated_circuit_reference(reference)
            or reference_key in dnp_references
            or lookup_unique_casefold(observed.components, reference) is None
        ):
            continue

        pin_role = serial_function_role_and_channel(function)
        if pin_role is None:
            continue
        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        if inventory is None or number.casefold() not in {item.casefold() for item in inventory}:
            continue

        assigned_nets = nets_by_pin.get(folded_pin, set())
        if len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        net_role = serial_function_role_and_channel(net)
        if (
            net_role is None
            or net_role[0] == pin_role[0]
            or net_role[1] != pin_role[1]
            or not net_role[1].startswith(("uart", "usart"))
        ):
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {net}",
                message=(
                    f"The native serial pin function indicates {pin_role[0].upper()}, but the "
                    f"assigned net name {net!r} indicates {net_role[0].upper()}. Review the "
                    "part-specific pin map and naming convention; an explicit label is a "
                    "review clue, not a topology requirement."
                ),
                evidence={
                    "reference": (reference,),
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_role": (pin_role[0],),
                    "channel": (pin_role[1],),
                    "net": (net,),
                    "net_role": (net_role[0],),
                },
            )
        )
    return tuple(findings)
