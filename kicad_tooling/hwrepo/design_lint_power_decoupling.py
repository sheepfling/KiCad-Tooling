"""Evaluate project-authored IC decoupling minimums against native netlists."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from .capacitance_values import parse_capacitance_pf
from .casefold_mapping_lookup import lookup_unique_casefold
from .design_lint_types import Candidate
from .ic_decoupling_models import IcDecouplingMap, IcDecouplingRequirement
from .models import NetlistContract


def _pin_net_index(observed: NetlistContract) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            result.setdefault(pin.casefold(), set()).add(net)
    return result


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
        issues.append(f"{reference} footprint is {component.footprint}; expected {expected_footprint}")
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
    pin_nets: dict[str, set[str]], pin: str, expected_net: str
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


def _requirement_issues(
    observed: NetlistContract,
    requirement: IcDecouplingRequirement,
    pin_nets: dict[str, set[str]],
) -> tuple[tuple[str, ...], tuple[tuple[str, Decimal | None], ...]]:
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
    power_net_issue = _pin_assignment_issue(pin_nets, requirement.power_pin, requirement.power_net)
    if power_net_issue is not None:
        issues.append(power_net_issue)

    dnp = {reference.casefold() for reference in observed.dnp_components}
    cap_values: list[tuple[str, Decimal | None]] = []
    for capacitor in sorted(requirement.capacitors, key=lambda item: item.reference.casefold()):
        cap_issues = _component_identity_issues(
            observed,
            capacitor.reference,
            None,
            capacitor.expected_symbol,
            capacitor.expected_footprint,
        )
        # Capacitor values are checked numerically below, so their current value is not
        # treated as an expected identity field.
        component = lookup_unique_casefold(observed.components, capacitor.reference)
        if component is None:
            cap_issues = [
                f"{capacitor.reference} is missing or ambiguous in the native component inventory"
            ]
            parsed_value = None
        else:
            parsed_value = parse_capacitance_pf(component.value)
            if parsed_value is None:
                cap_issues.append(
                    f"{capacitor.reference} value {component.value} is not a supported capacitance"
                )
        if capacitor.reference.casefold() in dnp:
            cap_issues.append(f"{capacitor.reference} is DNP and does not count as fitted capacitance")
        cap_issues.extend(
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
                cap_issues.append(type_issue)
        for pin, expected_net in (
            (capacitor.power_pin, requirement.power_net),
            (capacitor.return_pin, requirement.return_net),
        ):
            assignment_issue = _pin_assignment_issue(pin_nets, pin, expected_net)
            if assignment_issue is not None:
                cap_issues.append(assignment_issue)
        issues.extend(cap_issues)
        cap_values.append((capacitor.reference, parsed_value))

    return tuple(issues), tuple(cap_values)


def ic_decoupling_candidates(
    observed: NetlistContract,
    requirements: IcDecouplingMap | None,
) -> tuple[Candidate, ...]:
    """Report only mapped identity/topology faults or values below authored minimums."""
    if requirements is None:
        return ()
    pin_nets = _pin_net_index(observed)
    map_sha256 = hashlib.sha256(requirements.model_dump_json().encode("utf-8")).hexdigest()
    found: list[Candidate] = []
    for requirement in sorted(requirements.requirements, key=lambda item: item.id.casefold()):
        issues, capacitor_values = _requirement_issues(observed, requirement, pin_nets)
        total_pf = (
            sum((value for _, value in capacitor_values if value is not None), Decimal(0))
            if not issues and all(value is not None for _, value in capacitor_values)
            else None
        )
        minimum_pf = Decimal(str(requirement.minimum_total_capacitance_pf))
        below_minimum = total_pf is not None and total_pf < minimum_pf
        if not issues and not below_minimum:
            continue
        if below_minimum:
            message = (
                f"The mapped fitted capacitor set totals {total_pf} pF, below the project-authored "
                f"minimum {minimum_pf} pF. Review the cited requirement and component network. "
                "Nominal schematic values do not establish tolerance, bias derating, placement, "
                "transient response, or physical return-path adequacy."
            )
        else:
            message = (
                "The source-bound netlist does not match the project-authored IC decoupling map: "
                + "; ".join(issues)
                + ". Review the exact identities, fitted state, pin inventory, and pin-to-net "
                "assignments before relying on the capacitance comparison."
            )
        evidence = {
            "requirement_id": (requirement.id,),
            "basis": (requirement.basis,),
            "ic_reference": (requirement.ic_reference,),
            "power_pin": (requirement.power_pin,),
            "power_net": (requirement.power_net,),
            "return_net": (requirement.return_net,),
            "capacitor_references": tuple(item.reference for item in requirement.capacitors),
            "capacitor_values_pf": tuple(
                f"{reference}={value if value is not None else 'unsupported'}"
                for reference, value in capacitor_values
            ),
            "minimum_total_capacitance_pf": (str(minimum_pf),),
            "observed_total_capacitance_pf": () if total_pf is None else (str(total_pf),),
            "requirement_sha256": (map_sha256,),
            "mapping_issues": tuple(issues),
        }
        found.append(
            Candidate(
                rule_id="power.ic_decoupling_below_project_minimum",
                subject=f"{requirement.id}: {requirement.power_pin}",
                message=message,
                evidence=evidence,
            )
        )
    return tuple(found)
