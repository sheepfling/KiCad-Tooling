"""Review one-sided open Ethernet PHY transmit or receive pairs."""

from __future__ import annotations

from .bus_signal_pairs import ethernet_data_pair_function_role
from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .design_lint_types import Candidate
from .models import NetlistContract

RULE_ID = "bus.ethernet_data_unconnected_pin"


def ethernet_data_unconnected_pin_candidates(
    observed: NetlistContract,
) -> tuple[Candidate, ...]:
    """Review exactly one open side of an otherwise assigned native Ethernet pair."""
    assignments: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), set()).add(net)

    roles_by_reference: dict[str, dict[tuple[str, str], list[tuple[str, str]]]] = {}
    pin_numbers_by_reference: dict[str, list[str]] = {}
    function_pins: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        reference, separator, number = pin.rpartition(".")
        if not separator:
            continue
        reference_key = reference.casefold()
        pin_numbers_by_reference.setdefault(reference_key, []).append(number.casefold())
        function_pins.setdefault(pin.casefold(), []).append((pin, function))
        role = ethernet_data_pair_function_role(function)
        if role is not None:
            roles_by_reference.setdefault(reference_key, {}).setdefault(role, []).append(
                (pin, function)
            )

    dnp = {reference.casefold() for reference in observed.dnp_components}
    findings: list[Candidate] = []
    for reference_key, roles in roles_by_reference.items():
        # Recover the spelling from a role pin and require one unambiguous native component.
        role_pin = next((items[0][0] for items in roles.values() if items), "")
        reference = role_pin.rpartition(".")[0]
        if (
            not reference
            or reference.casefold() != reference_key
            or not is_integrated_circuit_reference(reference)
            or reference_key in dnp
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

        for direction in ("TX", "RX"):
            positive = roles.get((direction, "positive"), [])
            negative = roles.get((direction, "negative"), [])
            if len(positive) != 1 or len(negative) != 1:
                continue
            positive_pin, positive_function = positive[0]
            negative_pin, negative_function = negative[0]
            if (
                len(function_pins.get(positive_pin.casefold(), ())) != 1
                or len(function_pins.get(negative_pin.casefold(), ())) != 1
            ):
                continue

            positive_nets = assignments.get(positive_pin.casefold(), set())
            negative_nets = assignments.get(negative_pin.casefold(), set())
            if len(positive_nets) == 0 and len(negative_nets) == 1:
                open_pin, open_function = positive_pin, positive_function
                paired_pin, paired_function = negative_pin, negative_function
                paired_net = next(iter(negative_nets))
                polarity = "positive"
            elif len(negative_nets) == 0 and len(positive_nets) == 1:
                open_pin, open_function = negative_pin, negative_function
                paired_pin, paired_function = positive_pin, positive_function
                paired_net = next(iter(positive_nets))
                polarity = "negative"
            else:
                continue

            findings.append(
                Candidate(
                    rule_id=RULE_ID,
                    subject=(
                        f"{open_pin}: {open_function} is open while {paired_function} "
                        f"{paired_pin} is assigned to {paired_net}"
                    ),
                    message=(
                        f"This Ethernet {direction} {polarity} pin is unassigned while its "
                        f"unique {direction} pair mate {paired_function} {paired_pin} has one "
                        "net assignment. Review whether the lane is intentionally partial or a "
                        "connection is missing. Native pin functions do not establish that the "
                        "lane is required or prove PCB routing."
                    ),
                    evidence={
                        open_pin: (),
                        "ethernet_direction": (direction,),
                        "ethernet_polarity": (polarity,),
                        "function": (open_function,),
                        "paired_pin": (paired_pin,),
                        "paired_function": (paired_function,),
                        "paired_net": (paired_net,),
                        "component_pin_inventory": tuple(sorted(inventory_numbers)),
                    },
                )
            )

    return tuple(sorted(findings, key=lambda item: (item.subject.casefold(), item.subject)))
