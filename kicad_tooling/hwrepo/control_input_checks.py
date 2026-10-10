"""Validate authored control input endpoints, drivers, and bias paths."""

from __future__ import annotations

from .control_input_inventory import OUTPUT_CAPABLE_TYPES
from .models import (
    ControlBiasResistorRequirement,
    ControlInputsAnalysis,
    ControlLocalBiasRequirement,
    ControlPinRequirement,
    ElectricalCheck,
    NetlistContract,
)
from .resistor_paths import DirectResistor, direct_resistors


def control_input_checks(
    spec: ControlInputsAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Check exact control endpoints, declared drivers, and explicit local bias paths."""
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)

    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_types = {
        pin.casefold(): value.casefold() for pin, value in observed.pin_electrical_types.items()
    }
    resistors = {item.reference.casefold(): item for item in direct_resistors(observed)}
    known_pins = {
        f"{reference}.{number}".casefold()
        for reference, numbers in observed.component_pin_numbers.items()
        for number in numbers
    }
    known_pins.update(pin.casefold() for pin in observed.pin_functions)
    known_pins.update(pin.casefold() for pin in observed.pin_electrical_types)
    known_pins.update(pin.casefold() for pins in observed.nets.values() for pin in pins)

    def endpoint_issues(endpoint: ControlPinRequirement, expected_net: str) -> list[str]:
        reference = endpoint.reference
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the native netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is marked DNP")
        actual_symbol = symbols.get(key)
        if actual_symbol != endpoint.symbol:
            issues.append(
                f"{actual_reference} symbol is {actual_symbol or 'unknown'}; expected {endpoint.symbol}"
            )
        if component.footprint != endpoint.footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {endpoint.footprint}"
            )
        pin = endpoint.pin
        pin_key = pin.casefold()
        if pin_key not in known_pins:
            issues.append(f"{pin} is absent from the native symbol pin inventory")
        actual_nets = pin_nets.get(pin_key, set())
        if actual_nets != {expected_net}:
            assigned = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
            issues.append(f"{pin} is assigned to {assigned}; expected {expected_net}")
        actual_type = pin_types.get(pin_key)
        if actual_type != endpoint.electrical_type:
            issues.append(
                f"{pin} electrical type is {actual_type or 'unavailable'}; expected {endpoint.electrical_type}"
            )
        return issues

    def identity_issues(reference: str, symbol: str, footprint: str) -> list[str]:
        key = reference.casefold()
        entry = components.get(key)
        if entry is None:
            return [f"{reference} is absent from the netlist"]
        actual_reference, component = entry
        issues: list[str] = []
        if key in dnp:
            issues.append(f"{actual_reference} is DNP but must be fitted")
        if symbols.get(key) != symbol:
            issues.append(
                f"{actual_reference} symbol is {symbols.get(key) or 'unknown'}; expected {symbol}"
            )
        if component.footprint != footprint:
            issues.append(
                f"{actual_reference} footprint is {component.footprint or 'empty'}; expected {footprint}"
            )
        return issues

    def bias_resistor_issues(
        requirement: ControlBiasResistorRequirement,
    ) -> list[str]:
        key = requirement.reference.casefold()
        issues = identity_issues(requirement.reference, requirement.symbol, requirement.footprint)
        actual: DirectResistor | None = resistors.get(key)
        if actual is None:
            if key not in dnp and key not in components:
                issues.append(f"{requirement.reference} is absent from the netlist")
            elif key not in dnp:
                issues.append(
                    f"{requirement.reference} is not a recognized fitted two-terminal resistor"
                )
            return issues
        expected_nets = {requirement.signal_net, requirement.bias_net}
        if {actual.first_net, actual.second_net} != expected_nets:
            issues.append(
                f"{requirement.reference} connects {actual.first_net}/{actual.second_net}; "
                f"expected {requirement.signal_net}/{requirement.bias_net}"
            )
        if not requirement.minimum_ohms <= actual.resistance_ohms <= requirement.maximum_ohms:
            issues.append(
                f"{requirement.reference} is {actual.resistance_ohms:g}Ω, outside "
                f"{requirement.minimum_ohms:g}–{requirement.maximum_ohms:g}Ω"
            )
        return issues

    checks: list[ElectricalCheck] = []
    for signal in spec.signals:
        base = f"control-inputs/{signal.id}"
        endpoint_failures = [
            f"{endpoint.pin}: {'; '.join(issues)}"
            for endpoint in signal.endpoints
            if (issues := endpoint_issues(endpoint, signal.signal_net))
        ]
        checks.append(
            ElectricalCheck(
                id=f"{base}/endpoints",
                status="FAIL" if endpoint_failures else "PASS",
                detail=(
                    "; ".join(endpoint_failures)
                    if endpoint_failures
                    else f"All {len(signal.endpoints)} declared control endpoints match {signal.signal_net} and their native pin types."
                ),
            )
        )

        declared_pins = {endpoint.pin.casefold() for endpoint in signal.endpoints}
        declared_drivers = [
            endpoint for endpoint in signal.endpoints if endpoint.role == "approved_driver"
        ]
        candidates = {
            pin.casefold()
            for pin in pin_nets
            if signal.signal_net in pin_nets[pin] and pin_types.get(pin) in OUTPUT_CAPABLE_TYPES
        }
        undisclosed = sorted(candidates - declared_pins)
        connected_drivers = [
            endpoint
            for endpoint in declared_drivers
            if pin_nets.get(endpoint.pin.casefold()) == {signal.signal_net}
            and pin_types.get(endpoint.pin.casefold()) == endpoint.electrical_type
        ]
        driver_failures: list[str] = []
        if undisclosed:
            driver_failures.append(
                "undeclared output-capable pins on control net: " + ", ".join(undisclosed)
            )
        if signal.driver_policy == "none" and connected_drivers:
            driver_failures.append("driver policy is none but approved drivers are connected")
        elif signal.driver_policy == "single" and len(connected_drivers) != 1:
            driver_failures.append(
                f"single-driver policy has {len(connected_drivers)} connected approved drivers"
            )
        elif signal.driver_policy == "shared_open_drain":
            if len(connected_drivers) < 2:
                driver_failures.append(
                    f"shared open-drain policy has {len(connected_drivers)} connected approved drivers"
                )
            elif any(
                pin_types.get(endpoint.pin.casefold()) not in {"open_collector", "open_emitter"}
                for endpoint in connected_drivers
            ):
                driver_failures.append("shared drivers are not all open-collector/emitter pins")
        elif signal.driver_policy == "reviewed_multiple" and len(connected_drivers) < 2:
            driver_failures.append(
                f"reviewed multiple-driver policy has {len(connected_drivers)} connected approved drivers"
            )
        if signal.driver_basis:
            policy = f"{signal.driver_policy} ({signal.driver_basis})"
        else:
            policy = signal.driver_policy
        checks.append(
            ElectricalCheck(
                id=f"{base}/drivers",
                status="FAIL" if driver_failures else "PASS",
                detail=(
                    "; ".join(driver_failures)
                    if driver_failures
                    else f"Declared {policy} policy matches {len(connected_drivers)} connected approved driver(s); no undisclosed output-capable symbol pins were found."
                ),
            )
        )

        if isinstance(signal.bias, ControlLocalBiasRequirement):
            bias_failures = [
                f"{resistor.reference}: {'; '.join(issues)}"
                for resistor in signal.bias.resistors
                if (issues := bias_resistor_issues(resistor))
            ]
            checks.append(
                ElectricalCheck(
                    id=f"{base}/bias",
                    status="FAIL" if bias_failures else "PASS",
                    detail=(
                        "; ".join(bias_failures)
                        if bias_failures
                        else f"{len(signal.bias.resistors)} declared local bias resistor path(s) match the source netlist."
                    ),
                )
            )
        else:
            checks.append(
                ElectricalCheck(
                    id=f"{base}/bias",
                    status="NOT_APPLICABLE",
                    detail=(
                        f"{signal.bias.mode} bias is explicitly declared: {signal.bias.reason}. "
                        "This schematic check cannot verify internal or off-board bias behavior."
                    ),
                )
            )
    return tuple(checks)
