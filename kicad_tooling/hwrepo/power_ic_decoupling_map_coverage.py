"""Check mapped IC decoupling contracts for omitted native supply pins."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .casefold_mapping_lookup import casefolded_unique_index
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
    component_unmapped_from_map: bool = False


def ic_decoupling_map_coverage_issues(
    observed: NetlistContract,
    requirements: IcDecouplingMap | None,
) -> tuple[IcDecouplingMapCoverageIssue, ...]:
    """Find fitted IC power inputs omitted from an authored decoupling map.

    A current map entry receives per-pin and identity checks. Fitted U/IC
    references with exported power-input metadata but no entry receive a
    component-level coverage prompt. A quiet result does not establish that a
    decoupling requirement applies or that the project has a complete physical
    IC inventory.
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

    components = casefolded_unique_index(
        {reference: (reference, component) for reference, component in observed.components.items()}
    )
    symbols = casefolded_unique_index(observed.component_symbols)
    inventories = casefolded_unique_index(
        {reference: tuple(numbers) for reference, numbers in observed.component_pin_numbers.items()}
    )
    pin_types = casefolded_unique_index(
        {pin: (pin, pin_type.casefold()) for pin, pin_type in observed.pin_electrical_types.items()}
    )
    pin_functions = casefolded_unique_index(observed.pin_functions)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    power_inputs_by_reference: dict[str, tuple[str, ...]] = {}
    for key, (actual_reference, _) in components.items():
        if not is_integrated_circuit_reference(actual_reference) or key in dnp:
            continue
        pins = tuple(
            sorted(
                (
                    display_pin
                    for pin_key, (display_pin, pin_type) in pin_types.items()
                    if pin_key.rsplit(".", 1)[0].casefold() == key
                    and pin_type == "power_in"
                    and not is_return_function(pin_functions.get(pin_key, ""))
                ),
                key=lambda pin: (pin.casefold(), pin),
            )
        )
        if pins:
            power_inputs_by_reference[key] = pins

    issues: list[IcDecouplingMapCoverageIssue] = []
    for key in sorted(set(mapped_pins) | set(power_inputs_by_reference)):
        if key not in mapped_pins:
            component_entry = components.get(key)
            if component_entry is None:
                continue
            actual_reference, _ = component_entry
            issues.append(
                IcDecouplingMapCoverageIssue(
                    reference=actual_reference,
                    symbol=symbols.get(key, ""),
                    native_power_input_pins=power_inputs_by_reference[key],
                    mapped_power_pins=(),
                    unmapped_power_input_pins=power_inputs_by_reference[key],
                    pin_type_unavailable_pins=(),
                    pin_inventory_unavailable=False,
                    pin_inventory_disagreement_pins=(),
                    stale_map_identity=False,
                    map_sha256=map_sha256,
                    component_unmapped_from_map=True,
                )
            )
            continue
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
                    component_unmapped_from_map=False,
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
