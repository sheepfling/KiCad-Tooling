"""Authored RS-485 topology checks against a source-bound KiCad netlist."""

from __future__ import annotations

from .bus_heuristics import DirectResistor, direct_resistors
from .models import (
    ElectricalCheck,
    NetlistContract,
    Rs485Analysis,
    Rs485BiasResistorRequirement,
    Rs485BusRequirement,
    Rs485DnpResistorRequirement,
    Rs485EndpointRequirement,
    Rs485InternalFailSafeRequirement,
    Rs485LocalBiasRequirement,
    Rs485RemoteBiasRequirement,
    Rs485SignalPairRequirement,
    Rs485TerminationEndpointRequirement,
    Rs485TerminationResistorRequirement,
)


def rs485_checks(spec: Rs485Analysis, observed: NetlistContract) -> tuple[ElectricalCheck, ...]:
    """Check authored pair, endpoint, termination, and bias maps without assuming limits."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

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
    resistors = {item.reference.casefold(): item for item in direct_resistors(observed)}

    def pin_issue(pin: str, expected_net: str) -> str | None:
        key = pin.casefold()
        if key not in known_pins:
            return f"{pin} is absent from the native symbol pin inventory"
        actual = pin_nets.get(key, set())
        if actual != {expected_net}:
            assigned = ", ".join(sorted(actual)) if actual else "unconnected"
            return f"{pin} is assigned to {assigned}; expected {expected_net}"
        return None

    def identity_issues(reference: str, symbol: str, footprint: str) -> list[str]:
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {symbol}"
            )
        if component.footprint != footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {footprint}"
            )
        return issues

    def endpoint_checks(
        bus_id: str, endpoint: Rs485EndpointRequirement
    ) -> tuple[list[ElectricalCheck], bool]:
        base = f"rs485/{bus_id}/endpoint/{endpoint.id}"
        identity_failures = identity_issues(endpoint.reference, endpoint.symbol, endpoint.footprint)
        pin_failures = [
            issue
            for requirement in endpoint.pins
            if (issue := pin_issue(requirement.pin, requirement.net)) is not None
        ]
        checks = [
            ElectricalCheck(
                id=f"{base}/identity",
                status="FAIL" if identity_failures else "PASS",
                detail=(
                    "; ".join(identity_failures)
                    if identity_failures
                    else f"{endpoint.reference} matches the authored RS-485 endpoint symbol and footprint."
                ),
            ),
            ElectricalCheck(
                id=f"{base}/pins",
                status="FAIL" if pin_failures else "PASS",
                detail=(
                    "; ".join(pin_failures)
                    if pin_failures
                    else f"All {len(endpoint.pins)} declared differential, control, and reference pin assignments match."
                ),
            ),
        ]
        return checks, not identity_failures and not pin_failures

    def resistor_issue(
        requirement: Rs485TerminationResistorRequirement | Rs485BiasResistorRequirement,
        expected_nets: frozenset[str],
    ) -> tuple[str | None, DirectResistor | None]:
        key = requirement.reference.casefold()
        actual = resistors.get(key)
        failures = identity_issues(requirement.reference, requirement.symbol, requirement.footprint)
        if actual is None:
            if key in dnp:
                failures.append(f"{requirement.reference} is DNP but must be fitted")
            elif key not in components:
                failures.append(f"{requirement.reference} is absent from the netlist")
            else:
                failures.append(
                    f"{requirement.reference} is not a recognized fitted two-terminal resistor"
                )
        elif {actual.first_net, actual.second_net} != set(expected_nets):
            failures.append(
                f"{requirement.reference} connects {actual.first_net}/{actual.second_net}; "
                f"expected {'/'.join(sorted(expected_nets))}"
            )
        if actual is not None and not (
            requirement.minimum_ohms <= actual.resistance_ohms <= requirement.maximum_ohms
        ):
            failures.append(
                f"{requirement.reference} is {actual.resistance_ohms:g}Ω, outside "
                f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
            )
        return ("; ".join(failures) if failures else None), actual

    def dnp_option_issues(requirement: Rs485DnpResistorRequirement) -> list[str]:
        key = requirement.reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{requirement.reference} is absent from the netlist"]
        actual_reference, component = entry
        failures: list[str] = []
        if key not in dnp:
            failures.append(f"{actual_reference} is fitted, expected DNP")
        if symbols.get(key) != requirement.symbol:
            failures.append(
                f"{actual_reference} symbol is {symbols.get(key) or 'unknown'}; expected {requirement.symbol}"
            )
        if component.footprint != requirement.footprint:
            failures.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {requirement.footprint}"
            )
        prefix = f"{actual_reference}.".casefold()
        pins = {pin for pin in known_pins if pin.startswith(prefix)}
        pin_numbers = observed.component_pin_numbers.get(actual_reference)
        assigned = [pin_nets.get(pin, set()) for pin in pins]
        expected = {requirement.first_net, requirement.second_net}
        if (
            len(pins) != 2
            or (pin_numbers is not None and len(pin_numbers) != 2)
            or any(len(nets) != 1 for nets in assigned)
            or {next(iter(nets)) for nets in assigned if len(nets) == 1} != expected
        ):
            failures.append(
                f"{actual_reference} does not map exactly across "
                f"{requirement.first_net}/{requirement.second_net}"
            )
        return failures

    def termination_checks(
        bus: Rs485BusRequirement,
        pair: Rs485SignalPairRequirement,
        endpoint: Rs485TerminationEndpointRequirement,
        known_refs: set[str],
    ) -> list[ElectricalCheck]:
        base = f"rs485/{bus.id}/pair/{pair.id}/termination/{endpoint.id}"
        if endpoint.topology in {"external", "not_required"}:
            checks = [
                ElectricalCheck(
                    id=base,
                    status="NOT_APPLICABLE",
                    detail=(
                        f"{endpoint.topology} termination is explicitly declared: {endpoint.basis}. "
                        "This netlist cannot verify off-board hardware or transmission-line suitability."
                    ),
                )
            ]
            if endpoint.expected_dnp_resistors:
                failures = [
                    issue
                    for option in endpoint.expected_dnp_resistors
                    for issue in dnp_option_issues(option)
                ]
                checks.append(
                    ElectricalCheck(
                        id=f"{base}/dnp-options",
                        status="FAIL" if failures else "PASS",
                        detail=(
                            "; ".join(failures)
                            if failures
                            else "Declared DNP termination options are present on the expected pair nets."
                        ),
                    )
                )
            return checks

        failures: list[str] = []
        details: list[str] = []
        observed_total = 0.0
        complete = True
        for requirement in endpoint.resistors:
            expected_nets = frozenset((requirement.first_net, requirement.second_net))
            issue, actual = resistor_issue(requirement, expected_nets)
            if issue is not None:
                failures.append(issue)
                complete = False
            if actual is not None:
                observed_total += actual.resistance_ohms
                details.append(f"{actual.reference}={actual.resistance_ohms:g}Ω")
                known_refs.add(actual.reference.casefold())
        return [
            ElectricalCheck(
                id=base,
                status="FAIL" if failures else "PASS",
                observed=observed_total if complete else None,
                unit="Ω",
                detail=(
                    f"{endpoint.topology} termination at {endpoint.id} on "
                    f"{pair.line_1_net}/{pair.line_2_net}: "
                    + ("; ".join(failures) if failures else ", ".join(details))
                    + "."
                ),
            )
        ]

    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        endpoint_states: dict[str, bool] = {}
        for endpoint in bus.endpoints:
            rows, passed = endpoint_checks(bus.id, endpoint)
            results.extend(rows)
            endpoint_states[endpoint.reference.casefold()] = (
                endpoint_states.get(endpoint.reference.casefold(), True) and passed
            )
        for peer_index, peer in enumerate(bus.external_peers, start=1):
            results.append(
                ElectricalCheck(
                    id=f"rs485/{bus.id}/external-peer/{peer_index}",
                    status="NOT_APPLICABLE",
                    detail=f"External RS-485 peer is outside this netlist: {peer}",
                )
            )

        for pair in bus.pairs:
            base = f"rs485/{bus.id}/pair/{pair.id}"
            expected_line_pins = [
                item
                for endpoint in bus.endpoints
                for item in endpoint.pins
                if item.pair_id == pair.id
            ]
            line_pin_failures = [
                issue
                for requirement in expected_line_pins
                if (issue := pin_issue(requirement.pin, requirement.net)) is not None
            ]
            pair_transceivers = {
                endpoint.reference.casefold()
                for endpoint in bus.endpoints
                if endpoint.kind == "transceiver"
                and any(pin.pair_id == pair.id for pin in endpoint.pins)
            }
            results.append(
                ElectricalCheck(
                    id=f"{base}/membership",
                    status="FAIL"
                    if line_pin_failures
                    or not pair_transceivers
                    or any(
                        not endpoint_states.get(reference, False) for reference in pair_transceivers
                    )
                    else "PASS",
                    detail=(
                        "; ".join(line_pin_failures)
                        if line_pin_failures
                        else (
                            "No local transceiver pins are mapped to this differential pair."
                            if not pair_transceivers
                            else f"{len(expected_line_pins)} authored pair-line pins match {pair.line_1_net}/{pair.line_2_net}."
                        )
                    ),
                )
            )

            declared_termination_refs: set[str] = set()
            for endpoint in pair.terminations:
                results.extend(termination_checks(bus, pair, endpoint, declared_termination_refs))
                declared_termination_refs.update(
                    option.reference.casefold() for option in endpoint.expected_dnp_resistors
                )
            pair_nets = {pair.line_1_net, pair.line_2_net}
            unlisted = [
                resistor
                for resistor in direct_resistors(observed)
                if {resistor.first_net, resistor.second_net} == pair_nets
                and resistor.reference.casefold() not in declared_termination_refs
            ]
            results.append(
                ElectricalCheck(
                    id=f"{base}/unlisted-termination",
                    status="FAIL" if unlisted else "PASS",
                    detail=(
                        "Unlisted fitted resistor(s) directly across this RS-485 pair: "
                        + ", ".join(
                            f"{item.reference}={item.resistance_ohms:g}Ω" for item in unlisted
                        )
                        if unlisted
                        else "No unlisted fitted resistor directly spans the declared pair."
                    ),
                )
            )

            bias = pair.bias
            bias_id = f"{base}/bias"
            if isinstance(bias, Rs485LocalBiasRequirement):
                failures: list[str] = []
                for role, requirement in (
                    ("pull-up", bias.pull_up),
                    ("pull-down", bias.pull_down),
                ):
                    issue, _ = resistor_issue(
                        requirement,
                        frozenset((requirement.bus_net, requirement.rail_net)),
                    )
                    if issue is not None:
                        failures.append(f"{role}: {issue}")
                results.append(
                    ElectricalCheck(
                        id=bias_id,
                        status="FAIL" if failures else "PASS",
                        detail=(
                            "; ".join(failures)
                            if failures
                            else f"Both authored local bias resistor paths match: {bias.pull_up.reference} and {bias.pull_down.reference}."
                        ),
                    )
                )
            elif isinstance(bias, Rs485InternalFailSafeRequirement):
                identity_ok = all(
                    endpoint_states.get(reference.casefold(), False)
                    for reference in bias.transceiver_references
                )
                results.append(
                    ElectricalCheck(
                        id=bias_id,
                        status="NOT_APPLICABLE" if identity_ok else "FAIL",
                        detail=(
                            f"Project declares internal receiver fail-safe behavior for {', '.join(bias.transceiver_references)}; identity and pin mapping are checked, but the device feature is not verified from the netlist."
                            if identity_ok
                            else "One or more declared internal-failsafe transceivers fail their source-bound identity or pin checks."
                        ),
                    )
                )
            elif isinstance(bias, Rs485RemoteBiasRequirement):
                results.append(
                    ElectricalCheck(
                        id=bias_id,
                        status="NOT_APPLICABLE",
                        detail=f"Remote bias is declared but cannot be verified from this board netlist: {bias.reason}",
                    )
                )
            else:
                results.append(
                    ElectricalCheck(
                        id=bias_id,
                        status="NOT_APPLICABLE",
                        detail=f"No local or remote bias requirement is declared: {bias.reason}",
                    )
                )
    return tuple(results)
