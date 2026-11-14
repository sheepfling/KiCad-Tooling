"""Check mapped IC decoupling contracts for omitted native supply pins."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .component_references import is_integrated_circuit_reference
from .connector_identity import is_return_function
from .ic_decoupling_models import IcDecouplingMap
from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class IcDecouplingMapCoverageIssue:
    """One mapped IC whose native power-input coverage needs review."""

    reference: str
    symbol: str
    native_power_input_pins: tuple[str, ...]
    mapped_power_pins: tuple[str, ...]
    unmapped_power_input_pins: tuple[str, ...]
    pin_type_unavailable_pins: tuple[str, ...]
    pin_inventory_unavailable: bool
    pin_inventory_disagreement_pins: tuple[str, ...]
    stale_map_identity: bool
    map_sha256: str


def ic_decoupling_map_coverage_issues(
    observed: NetlistContract,
    requirements: IcDecouplingMap | None,
) -> tuple[IcDecouplingMapCoverageIssue, ...]:
    """Find power-input pins omitted from a current, mapped IC's decoupling map.

    The optional map scopes this review to references it names. A quiet result
    does not establish that the project has a complete IC inventory or that a
    decoupling requirement applies.
    """
    if requirements is None:
        return ()

    map_sha256 = _map_sha256(requirements)
    mapped_pins: dict[str, set[str]] = {}
    identities: dict[str, set[tuple[str, str, str]]] = {}
    display_references: dict[str, str] = {}
    for item in requirements.requirements:
        key = item.ic_reference.casefold()
        mapped_pins.setdefault(key, set()).add(item.power_pin.rsplit(".", 1)[1].casefold())
        identities.setdefault(key, set()).add(
            (item.expected_ic_value, item.expected_ic_symbol, item.expected_ic_footprint)
        )
        display_references[key] = item.ic_reference

    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_types = {
        pin.casefold(): (pin, pin_type.casefold())
        for pin, pin_type in observed.pin_electrical_types.items()
    }
    pin_functions = {pin.casefold(): function for pin, function in observed.pin_functions.items()}
    dnp = {reference.casefold() for reference in observed.dnp_components}

    issues: list[IcDecouplingMapCoverageIssue] = []
    for key in sorted(mapped_pins):
        if not is_integrated_circuit_reference(display_references[key]):
            continue
        component_entry = components.get(key)
        if component_entry is None or key in dnp:
            continue

        actual_reference, component = component_entry
        symbol = symbols.get(key, "")
        expected_identities = identities[key]
        actual_identity = (component.value, symbol, component.footprint)
        stale_map_identity = len(expected_identities) != 1 or actual_identity not in (
            expected_identities
        )

        inventory = inventories.get(key, ())
        inventory_available = bool(inventory)
        inventory_numbers = {number.casefold() for number in inventory}
        typed_pins = {
            pin: value
            for pin, value in pin_types.items()
            if pin.rsplit(".", 1)[0].casefold() == key
        }
        disagreement_pins = {
            typed_pins[pin][0]
            for pin in typed_pins
            if inventory_available and pin.rsplit(".", 1)[1].casefold() not in inventory_numbers
        }
        if inventory_available:
            disagreement_pins.update(
                f"{actual_reference}.{number}"
                for number in mapped_pins[key]
                if number not in inventory_numbers
            )
        disagreement = tuple(sorted(disagreement_pins, key=lambda pin: (pin.casefold(), pin)))
        unavailable_types = tuple(
            sorted(
                (
                    f"{actual_reference}.{number}"
                    for number in inventory
                    if f"{actual_reference}.{number}".casefold() not in typed_pins
                    and number.casefold() not in mapped_pins[key]
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        native_power_inputs = tuple(
            sorted(
                (
                    typed_pins[pin][0]
                    for pin in typed_pins
                    if typed_pins[pin][1] == "power_in"
                    and not is_return_function(pin_functions.get(pin, ""))
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        mapped_power = tuple(
            sorted(
                (
                    f"{actual_reference}.{number}"
                    for number in inventory
                    if number.casefold() in mapped_pins[key]
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        unmapped = tuple(
            pin
            for pin in native_power_inputs
            if pin.rsplit(".", 1)[1].casefold() not in mapped_pins[key]
        )

        if (
            stale_map_identity
            or unmapped
            or unavailable_types
            or not inventory_available
            or disagreement
        ):
            issues.append(
                IcDecouplingMapCoverageIssue(
                    reference=actual_reference,
                    symbol=symbol,
                    native_power_input_pins=native_power_inputs,
                    mapped_power_pins=mapped_power,
                    unmapped_power_input_pins=unmapped,
                    pin_type_unavailable_pins=unavailable_types,
                    pin_inventory_unavailable=not inventory_available,
                    pin_inventory_disagreement_pins=disagreement,
                    stale_map_identity=stale_map_identity,
                    map_sha256=map_sha256,
                )
            )

    return tuple(sorted(issues, key=lambda issue: (issue.reference.casefold(), issue.reference)))


def _map_sha256(requirements: IcDecouplingMap) -> str:
    """Hash a canonical view so harmless requirement ordering stays stable."""
    payload = {
        "schema_version": requirements.schema_version,
        "requirements": [
            {
                "id": item.id,
                "basis": item.basis,
                "ic_reference": item.ic_reference,
                "expected_ic_value": item.expected_ic_value,
                "expected_ic_symbol": item.expected_ic_symbol,
                "expected_ic_footprint": item.expected_ic_footprint,
                "power_pin": item.power_pin,
                "power_net": item.power_net,
                "return_net": item.return_net,
                "minimum_total_capacitance_pf": item.minimum_total_capacitance_pf,
                "capacitors": [
                    {
                        "reference": capacitor.reference,
                        "expected_symbol": capacitor.expected_symbol,
                        "expected_footprint": capacitor.expected_footprint,
                        "power_pin": capacitor.power_pin,
                        "return_pin": capacitor.return_pin,
                    }
                    for capacitor in sorted(
                        item.capacitors,
                        key=lambda capacitor: (
                            capacitor.reference.casefold(),
                            capacitor.reference,
                        ),
                    )
                ],
            }
            for item in sorted(
                requirements.requirements,
                key=lambda requirement: (requirement.id.casefold(), requirement.id),
            )
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
