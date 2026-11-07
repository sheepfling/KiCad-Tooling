"""Exact netlist checks and constant-current estimate for mapped hold-up capacitors."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .capacitance_values import parse_capacitance_pf
from .capacitor_hold_up_models import (
    CapacitorHoldUpMap,
    CapacitorHoldUpMember,
    CapacitorHoldUpRequirement,
)
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
    """Compare every declared parallel member with the current native netlist."""
    assignments = netlist_pin_net_index(observed)
    issues: list[str] = []
    capacitances_pf: list[Decimal] = []
    all_members_have_supported_values = True
    for member in requirement.members:
        member_issues, capacitance_pf = _assess_member(observed, member, requirement, assignments)
        issues.extend(member_issues)
        if capacitance_pf is None:
            all_members_have_supported_values = False
        else:
            capacitances_pf.append(capacitance_pf)
    capacitance_pf: Decimal | None = None
    if all_members_have_supported_values and len(capacitances_pf) == len(requirement.members):
        with localcontext() as context:
            context.prec = 52
            capacitance_pf = sum(capacitances_pf, Decimal(0))
    estimated_ms: Decimal | None = None
    if capacitance_pf is not None:
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


def _assess_member(
    observed: NetlistContract,
    member: CapacitorHoldUpMember,
    requirement: CapacitorHoldUpRequirement,
    assignments: Mapping[str, AbstractSet[str]],
) -> tuple[tuple[str, ...], Decimal | None]:
    """Return exact identity/connectivity mismatches and the observed value."""
    reference = member.capacitor_reference
    component = lookup_unique_casefold(observed.components, reference)
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    issues: list[str] = []
    if component is None or symbol is None or inventory is None:
        issues.append(f"{reference} is missing or ambiguous in the native component inventory")
        return tuple(issues), None

    is_dnp = reference.casefold() in {item.casefold() for item in observed.dnp_components}
    if is_dnp:
        issues.append(f"{reference} is marked DNP")
    if component.value != member.expected_value:
        issues.append(
            f"{reference} value is {component.value!r}; expected {member.expected_value!r}"
        )
    if component.footprint != member.expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint!r}; "
            f"expected {member.expected_footprint!r}"
        )
    if component.part_id != member.expected_part_id:
        issues.append(
            f"{reference} PART_ID is {component.part_id!r}; expected {member.expected_part_id!r}"
        )
    if symbol != member.expected_symbol:
        issues.append(f"{reference} symbol is {symbol!r}; expected {member.expected_symbol!r}")

    expected_pins = {
        member.positive_pin.rsplit(".", 1)[1].casefold(),
        member.return_pin.rsplit(".", 1)[1].casefold(),
    }
    actual_pins = {pin.casefold() for pin in inventory}
    if len(actual_pins) != 2 or actual_pins != expected_pins:
        issues.append(
            f"{reference} pin inventory is {tuple(inventory)}; "
            f"expected exactly {tuple(sorted(expected_pins))}"
        )
    for pin, expected_net in (
        (member.positive_pin, requirement.positive_net),
        (member.return_pin, requirement.return_net),
    ):
        actual = _actual_net(assignments, pin)
        if actual != (expected_net,):
            rendered = ", ".join(actual) if actual else "unassigned"
            issues.append(f"{pin} is assigned to {rendered}; expected only {expected_net}")

    capacitance_pf = parse_capacitance_pf(component.value)
    if capacitance_pf is None:
        issues.append(f"{reference} value {component.value!r} is not a supported capacitance")
    if is_dnp:
        capacitance_pf = None
    return tuple(issues), capacitance_pf


def capacitor_hold_up_map_sha256(requirements: CapacitorHoldUpMap) -> str:
    """Digest the complete authored map used by a hold-up finding."""
    return hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
