"""Project-authored control-signal topology checks against native netlists."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .bus_heuristics import DirectResistor, direct_resistors
from .connector_pins import power_function_key
from .models import (
    ControlBiasResistorRequirement,
    ControlExternalBiasRequirement,
    ControlInputBiasHeuristicCoverage,
    ControlInputBiasHeuristicEntry,
    ControlInputsAnalysis,
    ControlInternalBiasRequirement,
    ControlLocalBiasRequirement,
    ControlNoBiasRequirement,
    ControlPinRequirement,
    ElectricalCheck,
    NetlistContract,
)
from .return_nets import is_return_like_net_name

_OUTPUT_CAPABLE_TYPES = frozenset(
    {
        "output",
        "bidirectional",
        "tri_state",
        "power_out",
        "open_collector",
        "open_emitter",
    }
)
_CONTROL_INPUT_TYPES = frozenset({"input", "input_low"})
_CONTROL_FUNCTION_FAMILIES = {
    "reset": "reset",
    "resetn": "reset",
    "nreset": "reset",
    "nrst": "reset",
    "rst": "reset",
    "rstn": "reset",
    "rstb": "reset",
    "resetb": "reset",
    "hreset": "reset",
    "rsti": "reset",
    "por": "reset",
    "perst": "reset",
    "perst0": "reset",
    "perstn": "reset",
    "en": "enable",
    "ena": "enable",
    "enb": "enable",
    "enn": "enable",
    "nen": "enable",
    "enable": "enable",
    "enablen": "enable",
    "enableb": "enable",
    "shdn": "enable",
    "shutdown": "enable",
    "powerdown": "enable",
    "standby": "enable",
    "boot": "boot/strap",
    "boot0": "boot/strap",
    "boot1": "boot/strap",
    "bootsel": "boot/strap",
    "bootmode": "boot/strap",
    "bootstrap": "boot/strap",
    "nrpiboot": "boot/strap",
    "strap0": "boot/strap",
    "strap1": "boot/strap",
}


@dataclass(frozen=True)
class UnconnectedControlInput:
    pin: str
    function: str
    family: str
    electrical_type: str


@dataclass(frozen=True)
class ConnectedControlInput:
    pin: str
    function: str
    family: str
    electrical_type: str
    net: str


@dataclass(frozen=True)
class ControlInputBiasGap:
    net: str
    controls: tuple[ConnectedControlInput, ...]
    output_capable_peers: tuple[str, ...]


def control_input_family(function: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "", function.casefold())
    family = _CONTROL_FUNCTION_FAMILIES.get(normalized)
    if family is not None:
        return family
    tokens = re.findall(r"[a-z0-9]+", function.casefold())
    return next(
        (
            _CONTROL_FUNCTION_FAMILIES[token]
            for expected_family in ("reset", "enable", "boot/strap")
            for token in tokens
            if _CONTROL_FUNCTION_FAMILIES.get(token) == expected_family
        ),
        None,
    )


def unconnected_control_inputs(observed: NetlistContract) -> tuple[UnconnectedControlInput, ...]:
    """Find unassigned input pins with a bounded reset, enable, or boot alias."""
    connected_pins = {pin.casefold() for pins in observed.nets.values() for pin in pins}
    dnp_components = {reference.casefold() for reference in observed.dnp_components}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    candidates: list[UnconnectedControlInput] = []
    for pin, function in observed.pin_functions.items():
        reference = pin.rsplit(".", maxsplit=1)[0].casefold()
        if reference in dnp_components:
            continue
        family = control_input_family(function)
        electrical_type = pin_types.get(pin.casefold(), "")
        if (
            family is not None
            and electrical_type in _CONTROL_INPUT_TYPES
            and pin.casefold() not in connected_pins
        ):
            candidates.append(
                UnconnectedControlInput(
                    pin=pin,
                    function=function,
                    family=family,
                    electrical_type=electrical_type,
                )
            )
    return tuple(sorted(candidates, key=lambda item: (item.pin.casefold(), item.function)))


def connected_control_inputs_without_visible_rail_resistor(
    observed: NetlistContract,
) -> tuple[ControlInputBiasGap, ...]:
    """Find connected reset/enable/boot inputs without a direct fitted resistor to a named rail."""
    pin_nets: dict[str, set[str]] = {}
    pins_by_net: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
            pins_by_net.setdefault(net, set()).add(pin)

    dnp_components = {reference.casefold() for reference in observed.dnp_components}
    pin_types = {
        pin.casefold(): value.strip().casefold()
        for pin, value in observed.pin_electrical_types.items()
    }
    controls_by_net: dict[str, list[ConnectedControlInput]] = {}
    for pin, function in observed.pin_functions.items():
        if pin.rsplit(".", maxsplit=1)[0].casefold() in dnp_components:
            continue
        family = control_input_family(function)
        electrical_type = pin_types.get(pin.casefold(), "")
        assigned_nets = pin_nets.get(pin.casefold(), set())
        if family is None or electrical_type not in _CONTROL_INPUT_TYPES or len(assigned_nets) != 1:
            continue
        net = next(iter(assigned_nets))
        controls_by_net.setdefault(net, []).append(
            ConnectedControlInput(
                pin=pin,
                function=function,
                family=family,
                electrical_type=electrical_type,
                net=net,
            )
        )

    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) is not None for pin in pins)
    }
    return_nets = {
        net
        for net, pins in observed.nets.items()
        if is_return_like_net_name(net)
        or any(is_return_like_net_name(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    rail_keys = {net.casefold() for net in positive_rails | return_nets}
    control_net_keys = {net.casefold() for net in controls_by_net}

    biased_signal_keys: set[str] = set()
    for resistor in direct_resistors(observed):
        first_key = resistor.first_net.casefold()
        second_key = resistor.second_net.casefold()
        if first_key in rail_keys and second_key in control_net_keys:
            biased_signal_keys.add(second_key)
        if second_key in rail_keys and first_key in control_net_keys:
            biased_signal_keys.add(first_key)

    gaps: list[ControlInputBiasGap] = []
    for net, controls in controls_by_net.items():
        net_key = net.casefold()
        if net_key in rail_keys or net_key in biased_signal_keys:
            continue
        control_keys = {item.pin.casefold() for item in controls}
        output_capable_peers = tuple(
            sorted(
                (
                    f"{pin}: {observed.pin_functions.get(pin, 'unknown function')} "
                    f"({pin_types.get(pin.casefold(), 'unknown type')})"
                    for pin in pins_by_net.get(net, set())
                    if pin.casefold() not in control_keys
                    and pin_types.get(pin.casefold()) in _OUTPUT_CAPABLE_TYPES
                ),
                key=str.casefold,
            )
        )
        gaps.append(
            ControlInputBiasGap(
                net=net,
                controls=tuple(
                    sorted(controls, key=lambda item: (item.pin.casefold(), item.function))
                ),
                output_capable_peers=output_capable_peers,
            )
        )
    return tuple(sorted(gaps, key=lambda item: (item.net.casefold(), item.net)))


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
            if signal.signal_net in pin_nets[pin] and pin_types.get(pin) in _OUTPUT_CAPABLE_TYPES
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


def control_input_bias_heuristic_coverage(
    observed: NetlistContract,
    *,
    netlist_sha256: str,
    source_path: str | None,
    source_sha256: str | None,
    state: str,
    spec: ControlInputsAnalysis | None = None,
) -> ControlInputBiasHeuristicCoverage:
    """Resolve heuristic prompts only with exact, passing project-authored requirements."""
    gaps = connected_control_inputs_without_visible_rail_resistor(observed)
    entries: list[ControlInputBiasHeuristicEntry] = []
    if spec is None:
        reason = {
            "pending": "Project control-input review is pending; no bias decision can resolve this prompt.",
            "not_applicable": "The project marks control-input analysis not applicable; no net-specific bias decision resolves this prompt.",
        }.get(state, "No project-authored control-input requirement covers this candidate.")
        entries.extend(
            ControlInputBiasHeuristicEntry(
                net=gap.net,
                control_pins=tuple(item.pin for item in gap.controls),
                status="OPEN",
                issues=(reason,),
            )
            for gap in gaps
        )
        coverage_status: Literal[
            "NOT_CONFIGURED", "PENDING", "NOT_APPLICABLE", "COMPLETE", "OPEN", "BLOCKED"
        ]
        if state == "pending":
            coverage_status = "PENDING"
        elif state == "not_applicable":
            coverage_status = "NOT_APPLICABLE"
        elif state == "blocked":
            coverage_status = "BLOCKED"
        else:
            coverage_status = "NOT_CONFIGURED"
        return ControlInputBiasHeuristicCoverage(
            status=coverage_status,
            source_path=source_path,
            source_sha256=source_sha256,
            netlist_sha256=netlist_sha256 if gaps else None,
            entries=tuple(entries),
            issue=(
                "Could not load the project control-input contract." if state == "blocked" else None
            ),
        )

    checks_by_id = {item.id: item for item in control_input_checks(spec, observed)}
    for gap in gaps:
        candidate_pins = {item.pin.casefold() for item in gap.controls}
        matching = [
            signal
            for signal in spec.signals
            if signal.signal_net.casefold() == gap.net.casefold()
            and candidate_pins
            <= {
                endpoint.pin.casefold()
                for endpoint in signal.endpoints
                if endpoint.role == "controlled_input"
            }
        ]
        if len(matching) != 1:
            issue = (
                "No unique control-input requirement names this exact signal net and every detected input pin."
                if not matching
                else "More than one control-input requirement matches this signal net and input set."
            )
            entries.append(
                ControlInputBiasHeuristicEntry(
                    net=gap.net,
                    control_pins=tuple(item.pin for item in gap.controls),
                    status="OPEN",
                    issues=(issue,),
                )
            )
            continue

        signal = matching[0]
        prefix = f"control-inputs/{signal.id}/"
        relevant = {
            key.rsplit("/", maxsplit=1)[-1]: value
            for key, value in checks_by_id.items()
            if key.startswith(prefix)
        }
        issues = tuple(
            f"{name}: {check.detail}"
            for name, check in sorted(relevant.items())
            if (name == "endpoints" and check.status != "PASS")
            or (name == "drivers" and check.status != "PASS")
            or (name == "bias" and check.status not in {"PASS", "NOT_APPLICABLE"})
        )
        bias = signal.bias
        bias_reason = (
            bias.reason
            if isinstance(
                bias,
                (
                    ControlInternalBiasRequirement,
                    ControlExternalBiasRequirement,
                    ControlNoBiasRequirement,
                ),
            )
            else None
        )
        entries.append(
            ControlInputBiasHeuristicEntry(
                net=gap.net,
                control_pins=tuple(item.pin for item in gap.controls),
                signal_id=signal.id,
                bias_mode=bias.mode,
                bias_basis=bias.basis,
                bias_reason=bias_reason,
                status="OPEN" if issues else "COVERED",
                issues=issues,
            )
        )

    status: Literal["OPEN", "COMPLETE"] = (
        "OPEN" if any(item.status == "OPEN" for item in entries) else "COMPLETE"
    )
    return ControlInputBiasHeuristicCoverage(
        status=status,
        source_path=source_path,
        source_sha256=source_sha256,
        netlist_sha256=netlist_sha256 if gaps else None,
        entries=tuple(entries),
    )
