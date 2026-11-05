"""Shared source evidence for fitted IC pins assigned to named rails."""

from __future__ import annotations

from dataclasses import dataclass

from .casefold_mapping_lookup import lookup_unique_casefold
from .component_references import is_integrated_circuit_reference
from .named_rail_roles import named_rail_role_clue
from .netlist_contract_models import NetlistContract


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


@dataclass(frozen=True, slots=True)
class NamedRailPinSource:
    """One extracted named-rail pin bound to its source netlist."""

    observed: NetlistContract
    evidence: NamedRailPinEvidence

    def __post_init__(self) -> None:
        if not named_rail_pin_evidence_matches_source(self.observed, self.evidence):
            raise ValueError("Named-rail pin evidence must match its current native netlist")


def named_rail_pin_evidence_matches_source(
    observed: NetlistContract,
    evidence: NamedRailPinEvidence,
) -> bool:
    """Check one extracted rail pin against the current fitted native source."""
    reference, separator, number = evidence.pin.rpartition(".")
    if (
        not separator
        or reference.casefold() != evidence.reference.casefold()
        or number != evidence.number
        or not is_integrated_circuit_reference(reference)
        or lookup_unique_casefold(observed.components, evidence.reference) is None
        or evidence.reference.casefold() in {item.casefold() for item in observed.dnp_components}
        or lookup_unique_casefold(observed.pin_functions, evidence.pin) != evidence.function
    ):
        return False

    native_pins = tuple(
        pin for pin in observed.pin_functions if pin.casefold() == evidence.pin.casefold()
    )
    references = tuple(
        component
        for component in observed.components
        if component.casefold() == evidence.reference.casefold()
    )
    inventories = tuple(
        inventory
        for reference_key, inventory in observed.component_pin_numbers.items()
        if reference_key.casefold() == evidence.reference.casefold()
    )
    if native_pins != (evidence.pin,) or len(references) != 1 or len(inventories) != 1:
        return False

    inventory_keys = tuple(sorted(number.casefold() for number in inventories[0]))
    if (
        len(set(inventory_keys)) != len(inventories[0])
        or number.casefold() not in inventory_keys
        or inventory_keys != evidence.inventory
    ):
        return False

    assigned_nets = {
        net
        for net, pins in observed.nets.items()
        if any(pin.casefold() == evidence.pin.casefold() for pin in pins)
    }
    return (
        len(assigned_nets) == 1
        and evidence.net_name in assigned_nets
        and named_rail_role_clue(evidence.net_name) == evidence.rail_role
    )


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
