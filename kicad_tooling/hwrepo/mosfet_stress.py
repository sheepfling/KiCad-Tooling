"""Compare authored MOSFET operating-state stress with sourced terminal ratings."""

from __future__ import annotations

from .models import (
    ElectricalCheck,
    NetlistContract,
)
from .mosfet_stress_models import (
    MosfetOperatingState,
    MosfetStressAnalysis,
    MosfetStressRequirement,
    MosfetVoltageInterval,
)


def _maximum_absolute_difference(
    first: MosfetVoltageInterval, second: MosfetVoltageInterval
) -> float:
    """Return a conservative absolute-difference bound for independent intervals."""
    return max(
        abs(first.minimum_v - second.maximum_v),
        abs(first.maximum_v - second.minimum_v),
    )


def _terminal_assignments(
    requirement: MosfetStressRequirement,
) -> tuple[tuple[str, str, str, str], ...]:
    return (
        ("drain", requirement.drain_pin, requirement.drain_function, requirement.drain_net),
        ("gate", requirement.gate_pin, requirement.gate_function, requirement.gate_net),
        ("source", requirement.source_pin, requirement.source_function, requirement.source_net),
    )


def _terminal_checks(
    requirement: MosfetStressRequirement,
    observed: NetlistContract,
    *,
    base: str,
) -> tuple[tuple[ElectricalCheck, ...], bool]:
    terminals = _terminal_assignments(requirement)
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
    functions = {pin.casefold(): value for pin, value in observed.pin_functions.items()}

    checks: list[ElectricalCheck] = []
    all_ok = True
    for role, pin, function, net in terminals:
        key = pin.casefold()
        issues: list[str] = []
        if key not in known_pins:
            issues.append(f"{pin} is absent from the native symbol pin inventory")
        actual_function = functions.get(key)
        if actual_function != function:
            issues.append(f"native function is {actual_function or 'unknown'}; expected {function}")
        assigned_nets = pin_nets.get(key, set())
        if assigned_nets != {net}:
            observed_nets = ", ".join(sorted(assigned_nets)) if assigned_nets else "unconnected"
            issues.append(f"native nets are {observed_nets}; expected {net}")
        passed = not issues
        all_ok = all_ok and passed
        checks.append(
            ElectricalCheck(
                id=f"{base}/pin-{role}",
                status="PASS" if passed else "FAIL",
                detail=(
                    f"{pin} matches native function {function} and net {net}."
                    if passed
                    else f"{role.title()} pin {pin}: {'; '.join(issues)}."
                ),
            )
        )
    return tuple(checks), all_ok


def _identity_check(
    requirement: MosfetStressRequirement, observed: NetlistContract, *, base: str
) -> tuple[ElectricalCheck, bool]:
    reference_key = requirement.reference.casefold()
    components = {key.casefold(): value for key, value in observed.components.items()}
    symbols = {key.casefold(): value for key, value in observed.component_symbols.items()}
    pin_numbers = {
        key.casefold(): {number.casefold() for number in value}
        for key, value in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    component = components.get(reference_key)
    issues: list[str] = []
    if component is None:
        issues.append(f"{requirement.reference} is absent from the native netlist")
    else:
        if reference_key in dnp:
            issues.append(f"{requirement.reference} is marked DNP")
        actual_symbol = symbols.get(reference_key)
        if actual_symbol != requirement.expected_symbol:
            issues.append(
                f"symbol is {actual_symbol or 'unknown'}; expected {requirement.expected_symbol}"
            )
        if component.footprint != requirement.expected_footprint:
            issues.append(
                f"footprint is {component.footprint or 'empty'}; "
                f"expected {requirement.expected_footprint}"
            )
        if component.part_id != requirement.expected_part_id:
            issues.append(
                f"PART_ID is {component.part_id or 'missing'}; "
                f"expected {requirement.expected_part_id}"
            )
        terminals = _terminal_assignments(requirement)
        expected_numbers = {pin.rsplit(".", maxsplit=1)[1].casefold() for _, pin, _, _ in terminals}
        actual_numbers = pin_numbers.get(reference_key)
        if actual_numbers != expected_numbers:
            issues.append(
                f"native pin inventory is {', '.join(sorted(actual_numbers or ())) or 'unknown'}; "
                f"expected {', '.join(sorted(expected_numbers))}"
            )
    passed = not issues
    return (
        ElectricalCheck(
            id=f"{base}/identity",
            status="PASS" if passed else "FAIL",
            detail=(
                f"{requirement.reference} matches the reviewed symbol, footprint, PART_ID, "
                "population, and exact three-pin inventory."
                if passed
                else f"{requirement.reference}: {'; '.join(issues)}."
            ),
        ),
        passed,
    )


def _state_stress_checks(
    requirement: MosfetStressRequirement,
    state_id: str,
    state: MosfetOperatingState | None,
    *,
    identity_ok: bool,
    terminals_ok: bool,
    base: str,
) -> tuple[ElectricalCheck, ...]:
    state_base = f"{base}/state-{state_id}"
    terminal_nets = {net for _, _, _, net in _terminal_assignments(requirement)}
    missing = (
        sorted(terminal_nets)
        if state is None
        else sorted(terminal_nets - set(state.net_potentials))
    )
    coverage_ok = not missing
    checks: list[ElectricalCheck] = [
        ElectricalCheck(
            id=f"{state_base}/coverage",
            status="PASS" if coverage_ok else "FAIL",
            detail=(
                f"Required operating state {state_id} supplies potential intervals for all "
                "three terminal nets."
                if coverage_ok
                else (
                    f"Required operating state {state_id} is missing; expected potential "
                    f"coverage for {', '.join(missing)}."
                    if state is None
                    else f"Required operating state {state_id} is missing potential intervals for "
                    f"{', '.join(missing)}."
                )
            ),
        )
    ]
    if not identity_ok or not terminals_ok or state is None:
        reason = (
            "Stress was not calculated because exact native identity, terminal mapping, and the "
            "required operating state must all be present."
        )
        checks.extend(
            ElectricalCheck(id=f"{state_base}/{name}", status="NOT_APPLICABLE", detail=reason)
            for name in ("vds", "vgs")
        )
        return tuple(checks)

    for name, positive_net, negative_net, rating in (
        ("vds", requirement.drain_net, requirement.source_net, requirement.rated_maximum_vds_v),
        ("vgs", requirement.gate_net, requirement.source_net, requirement.rated_maximum_vgs_v),
    ):
        metric_missing = tuple(
            net for net in (positive_net, negative_net) if net not in state.net_potentials
        )
        if metric_missing:
            checks.append(
                ElectricalCheck(
                    id=f"{state_base}/{name}",
                    status="NOT_APPLICABLE",
                    detail=(
                        f"{name.upper()} stress is unavailable because state {state_id} lacks "
                        f"potential intervals for {', '.join(metric_missing)}."
                    ),
                )
            )
            continue
        positive = state.net_potentials[positive_net]
        negative = state.net_potentials[negative_net]
        stress = _maximum_absolute_difference(positive, negative)
        utilization = stress / rating
        passed = utilization <= requirement.maximum_utilization_fraction
        checks.append(
            ElectricalCheck(
                id=f"{state_base}/{name}",
                status="PASS" if passed else "FAIL",
                detail=(
                    f"{state_id} conservative maximum |V{name[1:].upper()}| is {stress:g} V "
                    f"({utilization:.6g} of the {rating:g} V rated maximum); project limit is "
                    f"{requirement.maximum_utilization_fraction:.6g}. Independent terminal "
                    "intervals are combined conservatively. Rating: "
                    f"{requirement.rating_source} ({requirement.rating_conditions}); stress "
                    f"basis: {requirement.stress_basis}."
                ),
                observed=utilization,
                unit="fraction",
            )
        )
    return tuple(checks)


def mosfet_stress_checks(
    spec: MosfetStressAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Check exact MOSFET identity/topology and authored state-potential envelopes."""
    states = {state.id.casefold(): state for state in spec.states}
    checks: list[ElectricalCheck] = []
    for requirement in sorted(spec.requirements, key=lambda item: item.id.casefold()):
        base = f"mosfet-stress/{requirement.id}"
        identity, identity_ok = _identity_check(requirement, observed, base=base)
        terminal_checks, terminals_ok = _terminal_checks(requirement, observed, base=base)
        checks.extend((identity, *terminal_checks))
        for state_id in sorted(spec.required_states, key=str.casefold):
            state = states.get(state_id.casefold())
            checks.extend(
                _state_stress_checks(
                    requirement,
                    state_id,
                    state,
                    identity_ok=identity_ok,
                    terminals_ok=terminals_ok,
                    base=base,
                )
            )
    return tuple(checks)
