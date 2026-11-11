"""Check mapped components for unaccounted native supply pins."""

from __future__ import annotations

from dataclasses import dataclass

from .component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    component_supply_voltage_range_map_sha256,
)
from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class ComponentSupplyRangePinCoverageIssue:
    """One mapped component whose native supply-pin coverage is incomplete."""

    reference: str
    symbol: str
    map_sha256: str
    native_power_input_pins: tuple[str, ...]
    mapped_range_pins: tuple[str, ...]
    unmapped_power_input_pins: tuple[str, ...]
    pin_type_unavailable_pins: tuple[str, ...]
    pin_inventory_unavailable: bool = False
    pin_inventory_disagreement_pins: tuple[str, ...] = ()


def component_supply_range_pin_coverage_issues(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[ComponentSupplyRangePinCoverageIssue, ...]:
    """Find uncovered power-input pins on exact components selected by the map.

    A quiet result covers only references in the authored map and only when the
    native component identity, pin inventory, and electrical types support the
    comparison. This does not establish that a symbol represents every
    physical package pin.
    """
    if requirements is None:
        return ()

    map_sha256 = component_supply_voltage_range_map_sha256(requirements)
    mapped_by_reference: dict[str, set[str]] = {}
    references: dict[str, str] = {}
    expected_identities: dict[str, tuple[str, str, str]] = {}
    for requirement in requirements.requirements:
        key = requirement.reference.casefold()
        mapped_by_reference.setdefault(key, set()).add(
            requirement.pin.rsplit(".", maxsplit=1)[1].casefold()
        )
        references[key] = requirement.reference
        identity = (
            requirement.expected_symbol,
            requirement.expected_footprint,
            requirement.expected_part_id,
        )
        expected_identities.setdefault(key, identity)

    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_numbers = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_types = {
        pin.casefold(): (pin, pin_type.casefold())
        for pin, pin_type in observed.pin_electrical_types.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    issues: list[ComponentSupplyRangePinCoverageIssue] = []

    for key in sorted(mapped_by_reference):
        component_entry = components.get(key)
        if component_entry is None or key in dnp:
            continue
        actual_reference, component = component_entry
        expected_symbol, expected_footprint, expected_part_id = expected_identities[key]
        if (
            symbols.get(key) != expected_symbol
            or component.footprint != expected_footprint
            or component.part_id != expected_part_id
        ):
            continue

        inventory = pin_numbers.get(key, ())
        inventory_available = bool(inventory)
        inventory_numbers = {number.casefold() for number in inventory}
        mapped_numbers = mapped_by_reference[key]
        typed_pins = {pin for pin in pin_types if pin.rsplit(".", maxsplit=1)[0].casefold() == key}
        disagreement_pins = tuple(
            sorted(
                (
                    pin_types[pin][0]
                    for pin in typed_pins
                    if inventory_available
                    and pin.rsplit(".", maxsplit=1)[1].casefold() not in inventory_numbers
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        unknown_types = tuple(
            sorted(
                (
                    f"{actual_reference}.{number}"
                    for number in inventory
                    if f"{actual_reference}.{number}".casefold() not in pin_types
                    and number.casefold() not in mapped_numbers
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        power_inputs = tuple(
            sorted(
                (pin_types[pin][0] for pin in typed_pins if pin_types[pin][1] == "power_in"),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        mapped_pins = tuple(
            sorted(
                (
                    f"{actual_reference}.{number}"
                    for number in inventory
                    if number.casefold() in mapped_numbers
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        unmapped_pins = tuple(
            pin
            for pin in power_inputs
            if pin.rsplit(".", maxsplit=1)[1].casefold() not in mapped_numbers
        )
        if unmapped_pins or unknown_types or not inventory_available or disagreement_pins:
            issues.append(
                ComponentSupplyRangePinCoverageIssue(
                    reference=references[key],
                    symbol=expected_symbol,
                    map_sha256=map_sha256,
                    native_power_input_pins=power_inputs,
                    mapped_range_pins=mapped_pins,
                    unmapped_power_input_pins=unmapped_pins,
                    pin_type_unavailable_pins=unknown_types,
                    pin_inventory_unavailable=not inventory_available,
                    pin_inventory_disagreement_pins=disagreement_pins,
                )
            )

    return tuple(sorted(issues, key=lambda item: (item.reference.casefold(), item.reference)))
