"""Compare authored regulator-passive topology with native netlist evidence."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract
from .regulator_passive_models import (
    RegulatorPassiveComponentRequirement,
    RegulatorPassiveTopologyMap,
)


def _component_issues(
    requirement: RegulatorPassiveComponentRequirement,
    observed: NetlistContract,
) -> tuple[str, ...]:
    issues: list[str] = []
    component = lookup_unique_casefold(observed.components, requirement.reference)
    symbol = lookup_unique_casefold(observed.component_symbols, requirement.reference)
    if component is None:
        issues.append(f"{requirement.reference} is absent or ambiguous in the native netlist")
    else:
        if component.value != requirement.value:
            issues.append(
                f"{requirement.reference} value is {component.value!r}; expected {requirement.value!r}"
            )
        if component.footprint != requirement.footprint:
            issues.append(
                f"{requirement.reference} footprint is {component.footprint or '<empty>'}; "
                f"expected {requirement.footprint!r}"
            )
        if requirement.part_id is not None and (
            component.part_id is None
            or component.part_id.casefold() != requirement.part_id.casefold()
        ):
            issues.append(
                f"{requirement.reference} PART_ID is {component.part_id or '<missing>'}; "
                f"expected {requirement.part_id!r}"
            )
    if symbol != requirement.symbol:
        issues.append(
            f"{requirement.reference} symbol is {symbol or '<unknown>'}; "
            f"expected {requirement.symbol!r}"
        )
    if requirement.reference.casefold() in {item.casefold() for item in observed.dnp_components}:
        issues.append(f"{requirement.reference} is marked DNP but the map requires it fitted")

    actual_pins = lookup_unique_casefold(observed.component_pin_numbers, requirement.reference)
    expected_numbers = {item.pin.rsplit(".", 1)[1].casefold() for item in requirement.pins}
    if actual_pins is None:
        issues.append(f"{requirement.reference} native pin inventory is unavailable or ambiguous")
    elif {str(item).casefold() for item in actual_pins} != expected_numbers:
        issues.append(
            f"{requirement.reference} native pin inventory differs from the complete authored map"
        )

    for pin_requirement in requirement.pins:
        actual_nets = tuple(
            sorted(
                net
                for net, pins in observed.nets.items()
                if any(pin.casefold() == pin_requirement.pin.casefold() for pin in pins)
            )
        )
        expected_nets = () if pin_requirement.net is None else (pin_requirement.net,)
        if actual_nets != expected_nets:
            actual = ", ".join(actual_nets) if actual_nets else "unconnected"
            issues.append(
                f"{pin_requirement.pin} is assigned to {actual}; expected "
                f"{pin_requirement.net if pin_requirement.net is not None else 'unconnected'!r}"
            )
    return tuple(issues)


def regulator_passive_topology_issues(
    requirements: RegulatorPassiveTopologyMap,
    observed: NetlistContract,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return deterministic topology issues for each authored regulator entry."""
    results: list[tuple[str, tuple[str, ...]]] = []
    for item in requirements.requirements:
        regulator_issues = _component_issues(item.regulator, observed)
        variants = ((item.id, item.required_passives),) + tuple(
            (alternative.id, alternative.required_passives)
            for alternative in item.approved_alternatives
        )
        all_variant_references = {
            passive.component.reference.casefold()
            for _, passives in variants
            for passive in passives
        }
        dnp_references = {reference.casefold() for reference in observed.dnp_components}
        if regulator_issues:
            results.append((item.id, regulator_issues))
            continue
        variant_issues: list[str] = []
        matched_variant = False
        for variant_id, passives in variants:
            selected_references = {passive.component.reference.casefold() for passive in passives}
            variant_issue_set = {
                f"{passive.role}: {message}"
                for passive in passives
                for message in _component_issues(passive.component, observed)
            }
            for reference in all_variant_references - selected_references:
                if (
                    reference not in dnp_references
                    and lookup_unique_casefold(observed.components, reference) is not None
                ):
                    variant_issue_set.add(f"unselected variant component {reference} is fitted")
            issues = tuple(sorted(variant_issue_set))
            if not issues:
                matched_variant = True
                break
            variant_issues.extend(f"approved variant {variant_id!r}: {issue}" for issue in issues)
        if not matched_variant:
            results.append((item.id, tuple(sorted(set(variant_issues)))))
    return tuple(results)


def regulator_passive_pin_role_issues(
    requirements: RegulatorPassiveTopologyMap,
    observed: NetlistContract,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Compare only pin functions and electrical types explicitly named in the map."""
    results: list[tuple[str, tuple[str, ...]]] = []
    dnp = {reference.casefold() for reference in observed.dnp_components}
    for topology in requirements.requirements:
        mapped_components = (
            topology.regulator,
            *(item.component for item in topology.required_passives),
            *(
                passive.component
                for alternative in topology.approved_alternatives
                for passive in alternative.required_passives
            ),
        )
        seen: set[tuple[str, str, str]] = set()
        issues: set[str] = set()
        for component_requirement in mapped_components:
            component_key = component_requirement.reference.casefold()
            component = lookup_unique_casefold(observed.components, component_requirement.reference)
            symbol = lookup_unique_casefold(
                observed.component_symbols, component_requirement.reference
            )
            if (
                component is None
                or symbol != component_requirement.symbol
                or component.value != component_requirement.value
                or component.footprint != component_requirement.footprint
                or (
                    component_requirement.part_id is not None
                    and (
                        component.part_id is None
                        or component.part_id.casefold() != component_requirement.part_id.casefold()
                    )
                )
                or component_key in dnp
            ):
                continue
            actual_numbers = lookup_unique_casefold(
                observed.component_pin_numbers, component_requirement.reference
            )
            expected_numbers = {
                pin.pin.rsplit(".", 1)[1].casefold() for pin in component_requirement.pins
            }
            if actual_numbers is None or {str(item).casefold() for item in actual_numbers} != (
                expected_numbers
            ):
                continue
            for pin in component_requirement.pins:
                expected_function = pin.expected_function
                expected_type = pin.expected_electrical_type
                if expected_function is None and expected_type is None:
                    continue
                signature = (
                    pin.pin.casefold(),
                    expected_function.casefold() if expected_function else "",
                    expected_type.casefold() if expected_type else "",
                )
                if signature in seen:
                    continue
                seen.add(signature)
                if expected_function is not None:
                    actual_function = lookup_unique_casefold(observed.pin_functions, pin.pin)
                    if actual_function is None:
                        issues.add(f"{pin.pin} native pin function is unavailable or ambiguous")
                    elif actual_function.casefold() != expected_function.casefold():
                        issues.add(
                            f"{pin.pin} native function is {actual_function!r}; "
                            f"expected {expected_function!r}"
                        )
                if expected_type is not None:
                    actual_type = lookup_unique_casefold(observed.pin_electrical_types, pin.pin)
                    if actual_type is None:
                        issues.add(f"{pin.pin} native electrical type is unavailable or ambiguous")
                    elif actual_type.casefold() != expected_type.casefold():
                        issues.add(
                            f"{pin.pin} native electrical type is {actual_type!r}; "
                            f"expected {expected_type!r}"
                        )
        if issues:
            results.append((topology.id, tuple(sorted(issues, key=str.casefold))))
    return tuple(results)
