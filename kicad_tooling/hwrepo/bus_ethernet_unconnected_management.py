"""Review partially assigned Ethernet MDC/MDIO management pairs."""

from __future__ import annotations

from .bus_signal_pairs import ethernet_management_function_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_rule_types import DesignLintRuleId
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID: DesignLintRuleId = "bus.ethernet_management_unconnected_pin"


def ethernet_management_unconnected_pin_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Prompt when exactly one native MDC/MDIO pin is open beside its assigned mate."""
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, list[tuple[str, str]]] = {}
    pin_numbers_by_reference: dict[str, list[str]] = {}
    roles_by_reference: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if not separator:
            continue
        reference_key = reference.casefold()
        folded_pin = pin.casefold()
        functions_by_pin.setdefault(folded_pin, []).append((pin, function))
        pin_numbers_by_reference.setdefault(reference_key, []).append(number.casefold())
        role = ethernet_management_function_role(function)
        if role is not None:
            roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
                (pin, function)
            )

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    found: list[Candidate] = []
    for reference_key, roles in roles_by_reference.items():
        clock_pins = roles.get("clock", [])
        data_pins = roles.get("data", [])
        if len(clock_pins) != 1 or len(data_pins) != 1:
            continue
        clock_pin, clock_function = clock_pins[0]
        data_pin, data_function = data_pins[0]
        reference, _separator, _number = clock_pin.rpartition(".")
        if (
            reference.casefold() != reference_key
            or not is_integrated_circuit_reference(reference)
            or reference_key in dnp_references
            or lookup_unique_casefold(observed.components, reference) is None
        ):
            continue

        inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
        observed_numbers = pin_numbers_by_reference.get(reference_key, [])
        inventory_numbers = {number.casefold() for number in inventory or ()}
        if (
            inventory is None
            or not inventory_numbers
            or len(inventory_numbers) != len(inventory)
            or len(observed_numbers) != len(set(observed_numbers))
            or inventory_numbers != set(observed_numbers)
        ):
            continue

        if (
            len(functions_by_pin.get(clock_pin.casefold(), ())) != 1
            or len(functions_by_pin.get(data_pin.casefold(), ())) != 1
        ):
            continue

        clock_nets = assignments.get(clock_pin.casefold(), set())
        data_nets = assignments.get(data_pin.casefold(), set())
        if len(clock_nets) == 0 and len(data_nets) == 1:
            open_pin, open_function, open_role = clock_pin, clock_function, "clock"
            paired_pin, paired_function = data_pin, data_function
            paired_net = next(iter(data_nets))
        elif len(data_nets) == 0 and len(clock_nets) == 1:
            open_pin, open_function, open_role = data_pin, data_function, "data"
            paired_pin, paired_function = clock_pin, clock_function
            paired_net = next(iter(clock_nets))
        else:
            continue

        found.append(
            Candidate(
                rule_id=RULE_ID,
                subject=(
                    f"{open_pin}: {open_function} is open while {paired_function} "
                    f"{paired_pin} is assigned to {paired_net}"
                ),
                message=(
                    f"This Ethernet management {open_role} pin is unassigned while the unique "
                    f"{paired_function} pin {paired_pin} has one net assignment. Review whether "
                    "the management interface is intentionally partial or a connection is "
                    "missing. Native pin functions do not establish that both signals are "
                    "required or prove PCB routing."
                ),
                evidence={
                    open_pin: (),
                    "function": (open_function,),
                    "ethernet_management_role": (open_role,),
                    "paired_pin": (paired_pin,),
                    "paired_function": (paired_function,),
                    "paired_net": (paired_net,),
                    "component_pin_inventory": tuple(sorted(inventory_numbers)),
                },
            )
        )

    return tuple(sorted(found, key=lambda item: (item.subject.casefold(), item.subject)))
