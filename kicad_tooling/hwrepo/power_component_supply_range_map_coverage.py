"""Discover fitted IC supply pins absent from the authored range map."""

from __future__ import annotations

from dataclasses import dataclass

from .component_references import is_integrated_circuit_reference
from .component_supply_range_models import (
    ComponentSupplyVoltageRangeMap,
    component_supply_voltage_range_map_sha256,
)
from .netlist_contract_models import NetlistContract


@dataclass(frozen=True, slots=True)
class ComponentSupplyRangeMapCoverageIssue:
    """One fitted IC with native supply pins not covered by a current map entry."""

    reference: str
    symbol: str
    native_power_input_pins: tuple[str, ...]
    map_sha256: str
    stale_map_identity: bool = False


def component_supply_range_map_coverage_issues(
    observed: NetlistContract,
    requirements: ComponentSupplyVoltageRangeMap | None,
) -> tuple[ComponentSupplyRangeMapCoverageIssue, ...]:
    """Find fitted U/IC references with native power inputs but no exact map coverage.

    Discovery is limited to reference designators recognized by the shared
    integrated-circuit predicate and exported ``power_in`` metadata. It does
    not infer expected voltage, a required net, or physical package pins.
    """
    if requirements is None:
        return ()

    map_sha256 = component_supply_voltage_range_map_sha256(requirements)
    mapped_identities: dict[str, tuple[str, str, str]] = {}
    for requirement in requirements.requirements:
        mapped_identities.setdefault(
            requirement.reference.casefold(),
            (
                requirement.expected_symbol,
                requirement.expected_footprint,
                requirement.expected_part_id,
            ),
        )

    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    power_inputs_by_reference: dict[str, set[str]] = {}
    for pin, electrical_type in observed.pin_electrical_types.items():
        if "." not in pin or electrical_type.casefold() != "power_in":
            continue
        reference, _ = pin.rsplit(".", maxsplit=1)
        key = reference.casefold()
        if is_integrated_circuit_reference(reference) and key in components and key not in dnp:
            power_inputs_by_reference.setdefault(key, set()).add(pin)

    issues: list[ComponentSupplyRangeMapCoverageIssue] = []
    for key in sorted(power_inputs_by_reference):
        actual_reference, component = components[key]
        actual_symbol = symbols.get(key, "")
        expected_identity = mapped_identities.get(key)
        identity_matches = expected_identity == (
            actual_symbol,
            component.footprint,
            component.part_id,
        )
        if identity_matches:
            continue
        issues.append(
            ComponentSupplyRangeMapCoverageIssue(
                reference=actual_reference,
                symbol=actual_symbol,
                native_power_input_pins=tuple(
                    sorted(
                        power_inputs_by_reference[key],
                        key=lambda item: (item.casefold(), item),
                    )
                ),
                map_sha256=map_sha256,
                stale_map_identity=expected_identity is not None,
            )
        )

    return tuple(issues)
