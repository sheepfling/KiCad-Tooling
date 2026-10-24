"""Review UART/USART signal pins assigned directly to named rails."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract
from .named_rail_roles import named_rail_role_clue
from .serial_participants import serial_function_role_and_channel

RULE_ID: DesignLintRuleId = "bus.serial_signal_on_named_rail"


def serial_signal_on_named_rail_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Review a fitted IC's explicit UART/USART TX or RX pin on a named rail.

    Pin functions and net labels are clues for review. The candidate does not
    establish a required serial endpoint or prove an electrical defect.
    """
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        functions_by_pin.setdefault(pin.casefold(), []).append((pin, function))

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    candidates: list[Candidate] = []
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
        if inventory is None:
            continue
        inventory_keys = {item.casefold() for item in inventory}
        if len(inventory_keys) != len(inventory) or number.casefold() not in inventory_keys:
            continue

        assigned_nets = nets_by_pin.get(folded_pin, set())
        if len(assigned_nets) != 1:
            continue
        net_name = next(iter(assigned_nets))
        label_role = named_rail_role_clue(net_name)
        if label_role is None:
            continue

        role, channel = pin_role
        candidates.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{pin}: {function} on {label_role} net {net_name}",
                message=(
                    f"The native serial pin function indicates {role.upper()} on channel "
                    f"{channel!r}, while its single assigned net label ({net_name!r}) is "
                    f"recognized as {label_role}. Review whether this is an intentional rail "
                    "strap or a pin-assignment issue. The function and label are review clues, "
                    "not proof of electrical potential, required serial connectivity, or a "
                    "defect; this check does not assess PCB copper or physical continuity."
                ),
                evidence={
                    "pin": (pin,),
                    "pin_function": (function,),
                    "pin_role": (role,),
                    "serial_channel": (channel,),
                    "assigned_net": (net_name,),
                    "net_label_role_clue": (label_role,),
                    "component_pin_inventory": tuple(sorted(inventory_keys)),
                },
            )
        )

    return tuple(sorted(candidates, key=lambda item: (item.subject.casefold(), item.subject)))
