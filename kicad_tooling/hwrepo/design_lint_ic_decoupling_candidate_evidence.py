"""Typed source and review records for project-authored IC decoupling maps."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from decimal import Decimal

from .capacitance_values import parse_capacitance_pf
from .casefold_mapping_lookup import lookup_unique_casefold
from .ic_decoupling_models import IcDecouplingMap, IcDecouplingRequirement
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_index


@dataclass(frozen=True, slots=True)
class IcDecouplingCapacitorValue:
    """One current capacitor value parsed from the native component inventory."""

    reference: str
    capacitance_pf: Decimal | None


@dataclass(frozen=True, slots=True)
class IcDecouplingRequirementReview:
    """Exact issues and nominal values observed for one authored requirement."""

    issues: tuple[str, ...]
    capacitor_values: tuple[IcDecouplingCapacitorValue, ...]


def _component_identity_issues(
    observed: NetlistContract,
    reference: str,
    expected_value: str | None,
    expected_symbol: str,
    expected_footprint: str,
) -> list[str]:
    component = lookup_unique_casefold(observed.components, reference)
    symbol = lookup_unique_casefold(observed.component_symbols, reference)
    issues: list[str] = []
    if component is None or symbol is None:
        return [f"{reference} is missing or ambiguous in the native component inventory"]
    if expected_value is not None and component.value != expected_value:
        issues.append(f"{reference} value is {component.value}; expected {expected_value}")
    if component.footprint != expected_footprint:
        issues.append(
            f"{reference} footprint is {component.footprint}; expected {expected_footprint}"
        )
    if symbol != expected_symbol:
        issues.append(f"{reference} symbol is {symbol}; expected {expected_symbol}")
    return issues


def _component_pin_inventory_issues(
    observed: NetlistContract,
    reference: str,
    pins: tuple[str, ...],
    *,
    exact: bool,
) -> list[str]:
    inventory = lookup_unique_casefold(observed.component_pin_numbers, reference)
    if inventory is None:
        return [f"{reference} has no unique native pin inventory"]
    expected = tuple(pin.rsplit(".", 1)[1].casefold() for pin in pins)
    actual = tuple(pin.casefold() for pin in inventory)
    if exact and (len(actual) != len(expected) or set(actual) != set(expected)):
        return [f"{reference} pin inventory is {tuple(inventory)}; expected exactly {expected}"]
    if any(pin not in actual for pin in expected):
        return [f"{reference} pin inventory omits one or more mapped pins {expected}"]
    return []


def _pin_assignment_issue(
    pin_nets: Mapping[str, AbstractSet[str]], pin: str, expected_net: str
) -> str | None:
    actual = tuple(sorted(pin_nets.get(pin.casefold(), ()), key=str.casefold))
    if actual != (expected_net,):
        rendered = ", ".join(actual) if actual else "unassigned"
        return f"{pin} is assigned to {rendered}; expected only {expected_net}"
    return None


def _pin_type_issue(observed: NetlistContract, pin: str, expected: str) -> str | None:
    actual = lookup_unique_casefold(observed.pin_electrical_types, pin)
    if actual is None or actual.casefold() != expected:
        rendered = "missing" if actual is None else actual
        return f"{pin} electrical type is {rendered}; expected {expected}"
    return None


def review_ic_decoupling_requirement(
    observed: NetlistContract,
    requirement: IcDecouplingRequirement,
    pin_nets: Mapping[str, AbstractSet[str]] | None = None,
) -> IcDecouplingRequirementReview:
    """Recheck authored IC/capacitor identity, fit, inventory, and assignments."""
    assignments = netlist_pin_net_index(observed) if pin_nets is None else pin_nets
    issues = _component_identity_issues(
        observed,
        requirement.ic_reference,
        requirement.expected_ic_value,
        requirement.expected_ic_symbol,
        requirement.expected_ic_footprint,
    )
    issues.extend(
        _component_pin_inventory_issues(
            observed,
            requirement.ic_reference,
            (requirement.power_pin,),
            exact=False,
        )
    )
    power_type_issue = _pin_type_issue(observed, requirement.power_pin, "power_in")
    if power_type_issue is not None:
        issues.append(power_type_issue)
    power_net_issue = _pin_assignment_issue(
        assignments,
        requirement.power_pin,
        requirement.power_net,
    )
    if power_net_issue is not None:
        issues.append(power_net_issue)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    if requirement.ic_reference.casefold() in dnp:
        issues.append(
            f"{requirement.ic_reference} is DNP and the mapped decoupling requirement does not apply"
        )
    capacitor_values: list[IcDecouplingCapacitorValue] = []
    for capacitor in sorted(requirement.capacitors, key=lambda item: item.reference.casefold()):
        capacitor_issues = _component_identity_issues(
            observed,
            capacitor.reference,
            None,
            capacitor.expected_symbol,
            capacitor.expected_footprint,
        )
        component = lookup_unique_casefold(observed.components, capacitor.reference)
        if component is None:
            capacitor_issues = [
                f"{capacitor.reference} is missing or ambiguous in the native component inventory"
            ]
            parsed_value = None
        else:
            parsed_value = parse_capacitance_pf(component.value)
            if parsed_value is None:
                capacitor_issues.append(
                    f"{capacitor.reference} value {component.value} is not a supported capacitance"
                )
        if capacitor.reference.casefold() in dnp:
            capacitor_issues.append(
                f"{capacitor.reference} is DNP and does not count as fitted capacitance"
            )
        capacitor_issues.extend(
            _component_pin_inventory_issues(
                observed,
                capacitor.reference,
                (capacitor.power_pin, capacitor.return_pin),
                exact=True,
            )
        )
        for pin, expected_type in (
            (capacitor.power_pin, "passive"),
            (capacitor.return_pin, "passive"),
        ):
            type_issue = _pin_type_issue(observed, pin, expected_type)
            if type_issue is not None:
                capacitor_issues.append(type_issue)
        for pin, expected_net in (
            (capacitor.power_pin, requirement.power_net),
            (capacitor.return_pin, requirement.return_net),
        ):
            assignment_issue = _pin_assignment_issue(assignments, pin, expected_net)
            if assignment_issue is not None:
                capacitor_issues.append(assignment_issue)
        issues.extend(capacitor_issues)
        capacitor_values.append(
            IcDecouplingCapacitorValue(
                reference=capacitor.reference,
                capacitance_pf=parsed_value,
            )
        )

    return IcDecouplingRequirementReview(
        issues=tuple(issues),
        capacitor_values=tuple(capacitor_values),
    )


def ic_decoupling_total_pf(review: IcDecouplingRequirementReview) -> Decimal | None:
    """Return a nominal total only when the exact mapped network has no issues."""
    if review.issues or any(item.capacitance_pf is None for item in review.capacitor_values):
        return None
    return sum(
        (
            item.capacitance_pf
            for item in review.capacitor_values
            if item.capacitance_pf is not None
        ),
        Decimal(0),
    )


@dataclass(frozen=True, slots=True)
class IcDecouplingFindingEvidence:
    """One below-minimum or stale map finding bound to its current inputs."""

    observed: NetlistContract
    requirements: IcDecouplingMap
    requirement_id: str
    review: IcDecouplingRequirementReview
    total_pf: Decimal | None
    minimum_pf: Decimal

    def __post_init__(self) -> None:
        matches = tuple(
            item
            for item in self.requirements.requirements
            if item.id.casefold() == self.requirement_id.casefold()
        )
        if len(matches) != 1 or matches[0].id != self.requirement_id:
            raise ValueError("IC decoupling evidence requires one exact authored requirement")
        requirement = matches[0]
        current_review = review_ic_decoupling_requirement(self.observed, requirement)
        if self.review != current_review:
            raise ValueError("IC decoupling review must match the current netlist and map")
        if self.total_pf != ic_decoupling_total_pf(current_review):
            raise ValueError("IC decoupling total must match the current native capacitor values")
        if self.minimum_pf != Decimal(str(requirement.minimum_total_capacitance_pf)):
            raise ValueError("IC decoupling minimum must match the authored requirement")
        below_minimum = self.total_pf is not None and self.total_pf < self.minimum_pf
        if not current_review.issues and not below_minimum:
            raise ValueError("IC decoupling evidence requires a current review finding")

    @property
    def requirement(self) -> IcDecouplingRequirement:
        """Return the exact project-authored requirement retained by this source."""
        return next(
            item for item in self.requirements.requirements if item.id == self.requirement_id
        )

    @property
    def requirement_sha256(self) -> str:
        """Return the digest of the complete authored map used by the scan."""
        return hashlib.sha256(self.requirements.model_dump_json().encode("utf-8")).hexdigest()
