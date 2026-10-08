"""Authored power-source/load membership checks against a native netlist."""

from __future__ import annotations

from .models import (
    ElectricalCheck,
    NetlistContract,
    PowerConnectivityAnalysis,
    PowerPinEndpointRequirement,
    PowerSourceGroupRequirement,
)


def power_connectivity_checks(
    spec: PowerConnectivityAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare reviewed source and load pin assignments with the KiCad netlist."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}

    def endpoint_issues(endpoint: PowerPinEndpointRequirement, expected_net: str) -> list[str]:
        key = endpoint.reference.casefold()
        component_entry = components.get(key)
        if component_entry is None:
            return [f"{endpoint.reference} is absent from the netlist"]
        actual_reference, component = component_entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        if symbols.get(key) != endpoint.symbol:
            issues.append(
                f"{actual_reference} symbol is {symbols.get(key) or 'unknown'}; "
                f"expected {endpoint.symbol}"
            )
        if component.footprint != endpoint.footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; "
                f"expected {endpoint.footprint}"
            )
        for pin in endpoint.pins:
            pin_key = pin.casefold()
            reference, number = pin.rsplit(".", 1)
            inventory = pin_numbers.get(reference.casefold())
            if inventory is not None and number.casefold() not in inventory:
                issues.append(f"{pin} is absent from the native symbol pin inventory")
                continue
            if pin_key not in known_pins:
                issues.append(f"{pin} is absent from the native symbol pin inventory")
                continue
            actual_nets = pin_nets.get(pin_key, set())
            if actual_nets != {expected_net}:
                assigned = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
                issues.append(f"{pin} is assigned to {assigned}; expected {expected_net}")
        return issues

    def source_group_issues(
        group: PowerSourceGroupRequirement, expected_net: str
    ) -> tuple[list[str], list[str]]:
        endpoint_results = [
            (endpoint, endpoint_issues(endpoint, expected_net)) for endpoint in group.endpoints
        ]
        matching = [endpoint.reference for endpoint, issues in endpoint_results if not issues]
        if group.selection == "all":
            issues = [
                f"{endpoint.reference}: {'; '.join(found)}"
                for endpoint, found in endpoint_results
                if found
            ]
            return issues, matching
        if matching:
            return [], matching
        return [
            f"{endpoint.reference}: {'; '.join(found)}" for endpoint, found in endpoint_results
        ], matching

    results: list[ElectricalCheck] = []
    for rail in spec.rails:
        for group in rail.source_groups:
            failures, matching = source_group_issues(group, rail.net)
            results.append(
                ElectricalCheck(
                    id=f"power-connectivity/{rail.id}/source/{group.id}",
                    status="FAIL" if failures else "PASS",
                    detail=(
                        "; ".join(failures)
                        if failures
                        else (
                            f"All declared source endpoints match net {rail.net}."
                            if group.selection == "all"
                            else f"At least one declared alternative source endpoint matches net {rail.net}: {', '.join(matching)}."
                        )
                    ),
                )
            )
        for load in rail.loads:
            failures = [
                f"{endpoint.reference}: {'; '.join(issues)}"
                for endpoint in load.endpoints
                if (issues := endpoint_issues(endpoint, rail.net))
            ]
            results.append(
                ElectricalCheck(
                    id=f"power-connectivity/{rail.id}/load/{load.id}",
                    status="FAIL" if failures else "PASS",
                    detail=(
                        "; ".join(failures)
                        if failures
                        else f"All declared load endpoints match net {rail.net}."
                    ),
                )
            )
    return tuple(results)
