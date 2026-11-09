"""Compare authored active regulator-support pin roles with native metadata."""

from __future__ import annotations

from .casefold_mapping_lookup import lookup_unique_casefold
from .netlist_contract_models import NetlistContract
from .regulator_component_checks import regulator_component_identity_issues
from .regulator_support_models import RegulatorSupportPinNetMap, RegulatorSupportPinRoleMap


def regulator_support_pin_role_issues(
    requirements: RegulatorSupportPinRoleMap,
    observed: NetlistContract,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Return exact identity, inventory, or authored pin-role mismatches."""
    results: list[tuple[str, str, tuple[str, ...]]] = []
    for topology in requirements.requirements:
        for component in topology.components:
            issues = list(regulator_component_identity_issues(component, observed))
            if not issues:
                for pin in component.pins:
                    if pin.expected_function is not None:
                        actual = lookup_unique_casefold(observed.pin_functions, pin.pin)
                        if actual is None:
                            issues.append(
                                f"{pin.pin} native pin function is unavailable or ambiguous"
                            )
                        elif actual.casefold() != pin.expected_function.casefold():
                            issues.append(
                                f"{pin.pin} native function is {actual!r}; "
                                f"expected {pin.expected_function!r}"
                            )
                    if pin.expected_electrical_type is not None:
                        actual = lookup_unique_casefold(observed.pin_electrical_types, pin.pin)
                        if actual is None:
                            issues.append(
                                f"{pin.pin} native electrical type is unavailable or ambiguous"
                            )
                        elif actual.casefold() != pin.expected_electrical_type.casefold():
                            issues.append(
                                f"{pin.pin} native electrical type is {actual!r}; "
                                f"expected {pin.expected_electrical_type!r}"
                            )
            if issues:
                results.append(
                    (
                        topology.id,
                        component.reference,
                        tuple(sorted(issues, key=str.casefold)),
                    )
                )
    return tuple(sorted(results, key=lambda item: (item[0].casefold(), item[1].casefold())))


def regulator_support_pin_net_issues(
    requirements: RegulatorSupportPinNetMap,
    observed: NetlistContract,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Compare exact active-support identity and project-authored pin net assignments."""
    results: list[tuple[str, str, tuple[str, ...]]] = []
    for topology in requirements.requirements:
        for component in topology.components:
            issues = list(regulator_component_identity_issues(component, observed))
            if not issues:
                for pin in component.pins:
                    actual_nets = tuple(
                        sorted(
                            (
                                net
                                for net, members in observed.nets.items()
                                if any(
                                    member.casefold() == pin.pin.casefold() for member in members
                                )
                            ),
                            key=str.casefold,
                        )
                    )
                    expected_nets = () if pin.expected_net is None else (pin.expected_net,)
                    if tuple(item.casefold() for item in actual_nets) != tuple(
                        item.casefold() for item in expected_nets
                    ):
                        actual = ", ".join(actual_nets) if actual_nets else "unconnected"
                        expected = (
                            pin.expected_net if pin.expected_net is not None else "unconnected"
                        )
                        issues.append(f"{pin.pin} is assigned to {actual}; expected {expected!r}")
            if issues:
                results.append(
                    (
                        topology.id,
                        component.reference,
                        tuple(sorted(issues, key=str.casefold)),
                    )
                )
    return tuple(sorted(results, key=lambda item: (item[0].casefold(), item[1].casefold())))


def regulator_support_pin_net_coverage_issues(
    role_requirements: RegulatorSupportPinRoleMap,
    net_requirements: RegulatorSupportPinNetMap | None,
    observed: NetlistContract,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Find source-matched active support components missing pin-net map coverage."""
    net_topologies = (
        {}
        if net_requirements is None
        else {item.regulator_reference.casefold(): item for item in net_requirements.requirements}
    )
    results: list[tuple[str, str, tuple[str, ...]]] = []
    for topology in role_requirements.requirements:
        net_topology = net_topologies.get(topology.regulator_reference.casefold())
        for component in topology.components:
            if regulator_component_identity_issues(component, observed):
                continue
            if net_topology is None:
                issues = (
                    f"regulator {topology.regulator_reference} has no pin-to-net topology map",
                )
            else:
                net_component = next(
                    (
                        item
                        for item in net_topology.components
                        if item.reference.casefold() == component.reference.casefold()
                    ),
                    None,
                )
                if net_component is None:
                    issues = (f"{component.reference} has no pin-to-net map entry",)
                else:
                    mapped_pins = {item.pin.casefold() for item in net_component.pins}
                    missing_pins = tuple(
                        sorted(
                            (
                                item.pin
                                for item in component.pins
                                if item.pin.casefold() not in mapped_pins
                            ),
                            key=str.casefold,
                        )
                    )
                    issues = (
                        (f"pin-to-net map omits {', '.join(missing_pins)}",) if missing_pins else ()
                    )
            if issues:
                results.append((topology.id, component.reference, issues))
    return tuple(sorted(results, key=lambda item: (item[0].casefold(), item[1].casefold())))
