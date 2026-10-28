"""Shared source evidence for fitted IC pins assigned to named rails."""

from __future__ import annotations

from dataclasses import dataclass

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .models import NetlistContract
from .named_rail_roles import named_rail_role_clue


@dataclass(frozen=True, slots=True)
class NamedRailPinEvidence:
    """One fitted IC pin with a complete inventory and unambiguous rail assignment."""

    pin: str
    reference: str
    number: str
    function: str
    net_name: str
    rail_role: str
    inventory: tuple[str, ...]


def assigned_named_rail_ic_pins(observed: NetlistContract) -> tuple[NamedRailPinEvidence, ...]:
    """Collect fitted IC pins with exactly one native assignment to a named rail."""
    nets_by_pin: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            nets_by_pin.setdefault(pin.casefold(), set()).add(net)

    functions_by_pin: dict[str, list[tuple[str, str]]] = {}
    for pin, function in observed.pin_functions.items():
        functions_by_pin.setdefault(pin.casefold(), []).append((pin, function))

    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    evidence: list[NamedRailPinEvidence] = []
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
        rail_role = named_rail_role_clue(net_name)
        if rail_role is None:
            continue

        evidence.append(
            NamedRailPinEvidence(
                pin=pin,
                reference=reference,
                number=number,
                function=function,
                net_name=net_name,
                rail_role=rail_role,
                inventory=tuple(sorted(inventory_keys)),
            )
        )

    return tuple(sorted(evidence, key=lambda item: (item.pin.casefold(), item.pin)))
