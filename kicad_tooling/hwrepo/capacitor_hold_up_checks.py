"""Exact netlist checks and constant-current estimate for mapped hold-up capacitors."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .capacitance_values import parse_capacitance_pf
from .capacitor_hold_up_models import CapacitorHoldUpMap, CapacitorHoldUpRequirement
from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


@dataclass(frozen=True, slots=True)
class CapacitorHoldUpAssessment:
    """Current native-netlist comparison for one authored storage requirement."""

    requirement_id: str
    issues: tuple[str, ...]
    capacitance_pf: Decimal | None
    estimated_hold_up_ms: Decimal | None


def estimate_constant_current_hold_up_ms(
    capacitance_pf: Decimal,
    starting_voltage_v: float,
    minimum_load_voltage_v: float,
    maximum_load_current_ma: float,
) -> Decimal:
    """Compute C * delta-V / I in ms from nominal capacitance and authored bounds."""
    with localcontext() as context:
        context.prec = 50
        delta_voltage = Decimal(str(starting_voltage_v)) - Decimal(str(minimum_load_voltage_v))
        current_ma = Decimal(str(maximum_load_current_ma))
        return capacitance_pf * delta_voltage / current_ma * Decimal("0.000001")


def _actual_net(assignments: Mapping[str, AbstractSet[str]], pin: str) -> tuple[str, ...]:
    return tuple(sorted(assignments.get(pin.casefold(), ()), key=str.casefold))


def assess_capacitor_hold_up(
    observed: NetlistContract,
    requirement: CapacitorHoldUpRequirement,
) -> CapacitorHoldUpAssessment:
    """Compare one exact capacitor identity and pin map with the current netlist."""
    component = lookup_unique_casefold(observed.components, requirement.capacitor_reference)
    symbol = lookup_unique_casefold(observed.component_symbols, requirement.capacitor_reference)
    inventory = lookup_unique_casefold(
        observed.component_pin_numbers, requirement.capacitor_reference
    )
    issues: list[str] = []
    capacitance_pf: Decimal | None = None
    estimated_ms: Decimal | None = None
    if component is None or symbol is None or inventory is None:
        issues.append(
            f"{requirement.capacitor_reference} is missing or ambiguous in the native component inventory"
        )
    else:
        if requirement.capacitor_reference.casefold() in {
            reference.casefold() for reference in observed.dnp_components
        }:
            issues.append(f"{requirement.capacitor_reference} is marked DNP")
        if component.value != requirement.expected_value:
            issues.append(
                f"{requirement.capacitor_reference} value is {component.value!r}; "
                f"expected {requirement.expected_value!r}"
            )
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"{requirement.capacitor_reference} footprint is {component.footprint!r}; "
                f"expected {requirement.expected_footprint!r}"
            )
        if component.part_id != requirement.expected_part_id:
            issues.append(
                f"{requirement.capacitor_reference} PART_ID is {component.part_id!r}; "
                f"expected {requirement.expected_part_id!r}"
            )
        if symbol != requirement.expected_symbol:
            issues.append(
                f"{requirement.capacitor_reference} symbol is {symbol!r}; "
                f"expected {requirement.expected_symbol!r}"
            )
        expected_pins = {
            requirement.positive_pin.rsplit(".", 1)[1].casefold(),
            requirement.return_pin.rsplit(".", 1)[1].casefold(),
        }
        actual_pins = {pin.casefold() for pin in inventory}
        if len(actual_pins) != 2 or actual_pins != expected_pins:
            issues.append(
                f"{requirement.capacitor_reference} pin inventory is {tuple(inventory)}; "
                f"expected exactly {tuple(sorted(expected_pins))}"
            )
        assignments = netlist_pin_net_index(observed)
        for pin, expected_net in (
            (requirement.positive_pin, requirement.positive_net),
            (requirement.return_pin, requirement.return_net),
        ):
            actual = _actual_net(assignments, pin)
            if actual != (expected_net,):
                rendered = ", ".join(actual) if actual else "unassigned"
                issues.append(f"{pin} is assigned to {rendered}; expected only {expected_net}")
        capacitance_pf = parse_capacitance_pf(component.value)
        if capacitance_pf is None:
            issues.append(
                f"{requirement.capacitor_reference} value {component.value!r} "
                "is not a supported capacitance"
            )
        else:
            estimated_ms = estimate_constant_current_hold_up_ms(
                capacitance_pf,
                requirement.starting_voltage_v,
                requirement.minimum_load_voltage_v,
                requirement.maximum_load_current_ma,
            )
    return CapacitorHoldUpAssessment(
        requirement_id=requirement.id,
        issues=tuple(issues),
        capacitance_pf=capacitance_pf,
        estimated_hold_up_ms=estimated_ms,
    )


def capacitor_hold_up_map_sha256(requirements: CapacitorHoldUpMap) -> str:
    """Digest the complete authored map used by a hold-up finding."""
    return hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
