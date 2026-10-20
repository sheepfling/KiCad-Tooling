"""Shared bounded grouping and pin-inventory checks for connector aliases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .connector_identity import connector_candidate_references
from .models import NetlistContract


@dataclass(frozen=True)
class ConnectorFootprintPeerGroup:
    """Fitted connector candidates sharing an exact value and footprint key."""

    footprint_key: str
    value_key: str
    footprint: str
    value: str
    references: tuple[str, ...]


def connector_footprint_peer_candidate_groups(
    observed: NetlistContract,
    declared_references: tuple[str, ...] = (),
) -> tuple[ConnectorFootprintPeerGroup, ...]:
    """Group distinct connector symbols by nonempty value and footprint clues."""
    connector_references = {
        reference.casefold()
        for reference in connector_candidate_references(observed, declared_references)
    }
    dnp_references = {reference.casefold() for reference in observed.dnp_components}
    components = {
        reference.casefold(): component for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    grouped: dict[tuple[str, str], list[str]] = {}
    for reference, component in observed.components.items():
        reference_key = reference.casefold()
        symbol = symbols.get(reference_key)
        if (
            reference_key not in connector_references
            or reference_key in dnp_references
            or symbol is None
            or (component.part_id is not None and component.part_id.strip())
            or not component.value.strip()
            or not component.footprint.strip()
        ):
            continue
        identity = (component.footprint.strip().casefold(), component.value.strip().casefold())
        grouped.setdefault(identity, []).append(reference)

    result: list[ConnectorFootprintPeerGroup] = []
    for (footprint_key, value_key), references in sorted(grouped.items()):
        peers = tuple(sorted(references, key=lambda item: (item.casefold(), item)))
        if (
            len(peers) < 2
            or len({symbols[reference.casefold()].casefold() for reference in peers}) < 2
        ):
            continue
        representative = components[peers[0].casefold()]
        result.append(
            ConnectorFootprintPeerGroup(
                footprint_key=footprint_key,
                value_key=value_key,
                footprint=representative.footprint.strip(),
                value=representative.value.strip(),
                references=peers,
            )
        )
    return tuple(result)


def observed_connector_pin_numbers(observed: NetlistContract) -> dict[str, set[str]]:
    """Collect observed pin references that a full native inventory must cover."""
    found: dict[str, set[str]] = {}
    pin_groups = (
        observed.pin_functions,
        observed.pin_electrical_types,
        *observed.nets.values(),
        *observed.unconnected_nets.values(),
    )
    for assignments in pin_groups:
        pins = assignments.keys() if isinstance(assignments, Mapping) else assignments
        for pin in pins:
            reference, separator, number = pin.rpartition(".")
            if separator and reference and number:
                found.setdefault(reference.casefold(), set()).add(number.casefold())
    return found


def complete_connector_footprint_peer_pin_inventory(
    observed: NetlistContract,
    references: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, dict[str, str]]] | None:
    """Return matching complete pin inventories and their native display numbers."""
    wanted = {reference.casefold() for reference in references}
    inventories: dict[str, tuple[str, ...]] = {}
    for reference, numbers in observed.component_pin_numbers.items():
        reference_key = reference.casefold()
        if reference_key not in wanted:
            continue
        if reference_key in inventories:
            return None
        inventories[reference_key] = tuple(numbers)

    if any(reference.casefold() not in inventories for reference in references):
        return None
    displayed_numbers = {
        reference.casefold(): {
            number.casefold(): number for number in inventories[reference.casefold()]
        }
        for reference in references
    }
    folded_inventories = {
        reference: tuple(number.casefold() for number in inventories[reference])
        for reference in displayed_numbers
    }
    inventory_sets = {frozenset(numbers) for numbers in folded_inventories.values()}
    if (
        not inventory_sets
        or any(not numbers for numbers in folded_inventories.values())
        or any(len(set(numbers)) != len(numbers) for numbers in folded_inventories.values())
        or len(inventory_sets) != 1
    ):
        return None

    valid_numbers = next(iter(inventory_sets))
    observed_numbers = observed_connector_pin_numbers(observed)
    if any(
        not observed_numbers.get(reference.casefold(), set()).issubset(valid_numbers)
        for reference in references
    ):
        return None

    pin_numbers = tuple(
        displayed_numbers[references[0].casefold()][number]
        for number in sorted(valid_numbers, key=lambda item: (item.casefold(), item))
    )
    return pin_numbers, displayed_numbers
