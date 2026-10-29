"""Review a one-sided open RS-485 A/B bus-line pair."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract
from .rs485_data_functions import explicit_rs485_transceiver_identity
from .rs485_line_functions import rs485_bus_line_role

RULE_ID = "bus.rs485_unconnected_line_pin"


def rs485_unconnected_line_pin_candidates(observed: NetlistContract) -> tuple[Candidate, ...]:
    """Prompt when one exact A/B function is open beside its assigned mate."""
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    pins_by_reference: dict[str, list[tuple[str, str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if separator and reference and number:
            pins_by_reference.setdefault(reference.casefold(), []).append((pin, number, function))

    components = {reference.casefold(): reference for reference in observed.components}
    dnp = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for folded_reference, pin_functions in sorted(pins_by_reference.items()):
        reference = components.get(folded_reference)
        if (
            reference is None
            or folded_reference in dnp
            or not is_integrated_circuit_reference(reference)
        ):
            continue
        identity = explicit_rs485_transceiver_identity(observed, reference)
        if identity is None:
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        function_numbers = tuple(number.casefold() for _, number, _ in pin_functions)
        if (
            inventory is None
            or not inventory
            or len({number.casefold() for number in inventory}) != len(inventory)
            or len(set(function_numbers)) != len(function_numbers)
            or set(function_numbers) != {number.casefold() for number in inventory}
        ):
            continue

        role_pins: dict[str, list[tuple[str, str]]] = {"a": [], "b": []}
        for pin, _number, function in pin_functions:
            role = rs485_bus_line_role(function)
            if role is not None:
                role_pins[role].append((pin, function))
        if len(role_pins["a"]) != 1 or len(role_pins["b"]) != 1:
            continue

        a_pin, a_function = role_pins["a"][0]
        b_pin, b_function = role_pins["b"][0]
        a_nets = assignments.get(a_pin.casefold(), set())
        b_nets = assignments.get(b_pin.casefold(), set())
        if len(a_nets) == 1 and not b_nets:
            open_pin, open_function, role = b_pin, b_function, "b"
            paired_pin, paired_function, net = a_pin, a_function, next(iter(a_nets))
        elif len(b_nets) == 1 and not a_nets:
            open_pin, open_function, role = a_pin, a_function, "a"
            paired_pin, paired_function, net = b_pin, b_function, next(iter(b_nets))
        else:
            continue

        findings.append(
            Candidate(
                rule_id=RULE_ID,
                subject=f"{open_pin}: RS-485 {role.upper()} bus-line function is open",
                message=(
                    f"This explicitly identified RS-485 {role.upper()} bus-line pin is "
                    f"unassigned while its paired {paired_function} pin {paired_pin} has "
                    f"one assignment to {net}. Review whether the partial pair is intentional "
                    "or a connection is missing; identity and pin names do not establish "
                    "interface use or PCB routing."
                ),
                evidence={
                    "component": (reference,),
                    "open_pin": (open_pin,),
                    "open_function": (open_function,),
                    "open_role": (role,),
                    "paired_pin": (paired_pin,),
                    "paired_function": (paired_function,),
                    "paired_net": (net,),
                    "identity_basis": (identity,),
                    "component_pin_inventory": tuple(
                        sorted(number.casefold() for number in inventory)
                    ),
                },
            )
        )
    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
