"""I2c pullup contract for deterministic KiCad bus analysis."""

from __future__ import annotations

import math

from .connector_identity import power_function_key
from .i2c_pullup_contract_paths import (
    i2c_array_channel_issue,
    i2c_array_component_issues,
    i2c_series_path_check,
)
from .i2c_pullup_models import (
    I2cPullupAnalysis,
    I2cPullupLineRequirement,
    I2cPullupVoltageCompatibilityRequirement,
)
from .models import (
    ElectricalCheck,
    NetlistContract,
)
from .resistor_paths import direct_resistors


def i2c_pullup_checks(
    spec: I2cPullupAnalysis, observed: NetlistContract
) -> tuple[ElectricalCheck, ...]:
    """Compare authored bus ranges with direct, exact series, and mapped array paths."""
    resistors = direct_resistors(observed)
    components = {
        reference.casefold(): (reference, component)
        for reference, component in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    pin_numbers = {
        reference.casefold(): {number.casefold() for number in numbers}
        for reference, numbers in observed.component_pin_numbers.items()
    }
    dnp = {reference.casefold() for reference in observed.dnp_components}
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    array_component_issues = {
        array.reference.casefold(): i2c_array_component_issues(
            array, components, symbols, pin_numbers, dnp
        )
        for array in spec.arrays
    }
    positive_rails = {
        net
        for net, pins in observed.nets.items()
        if power_function_key(net) is not None
        or any(power_function_key(observed.pin_functions.get(pin, "")) for pin in pins)
    }
    results: list[ElectricalCheck] = []
    for bus in spec.buses:
        for name, line in (("SDA", bus.sda), ("SCL", bus.scl)):
            direct_paths = tuple(
                item
                for item in resistors
                if {item.first_net, item.second_net} == {line.net, line.rail}
            )
            mapped_channels = tuple(
                (array, channel)
                for array in spec.arrays
                for channel in array.channels
                if channel.signal_net == line.net and channel.rail_net == line.rail
            )
            array_values: list[float] = []
            array_path_names: list[str] = []
            array_failures: list[str] = []
            for array, channel in mapped_channels:
                channel_issues = list(array_component_issues[array.reference.casefold()])
                channel_issue = i2c_array_channel_issue(
                    array.reference,
                    channel.id,
                    channel.signal_pin,
                    channel.rail_pin,
                    line.net,
                    line.rail,
                    pin_nets,
                )
                if channel_issue is not None:
                    channel_issues.append(channel_issue)
                if channel_issues:
                    array_failures.extend(channel_issues)
                else:
                    array_values.append(channel.resistance_ohms)
                    array_path_names.append(
                        f"{array.reference}.{channel.id}={channel.resistance_ohms:g}Ω"
                    )
            series_values: list[float] = []
            series_path_names: list[str] = []
            series_failures: list[str] = []
            for series_path in spec.series_paths:
                if (series_path.signal_net, series_path.rail_net) != (line.net, line.rail):
                    continue
                series_check, series_value = i2c_series_path_check(
                    series_path,
                    observed,
                    resistors,
                    f"i2c-pullup/{bus.id}/{name.casefold()}/series/{series_path.id}",
                )
                results.append(series_check)
                if series_value is None:
                    series_failures.append(series_check.detail)
                else:
                    series_values.append(series_value)
                    series_path_names.append(
                        f"{' + '.join(item.reference for item in series_path.resistors)}="
                        f"{series_value:g}Ω"
                    )
            unexpected_rails = tuple(
                item
                for item in resistors
                if line.net in {item.first_net, item.second_net}
                and (
                    other_net := (item.second_net if item.first_net == line.net else item.first_net)
                )
                in positive_rails
                and other_net != line.rail
            )
            path_values = (
                [item.resistance_ohms for item in direct_paths] + array_values + series_values
            )
            equivalent = 1 / sum(1 / value for value in path_values) if path_values else None
            passed = (
                equivalent is not None
                and line.minimum_ohms <= equivalent <= line.maximum_ohms
                and not unexpected_rails
                and not array_failures
                and not series_failures
            )
            details = [f"{item.reference}={item.resistance_ohms:g}Ω" for item in direct_paths]
            path_summary = ", ".join((*details, *array_path_names, *series_path_names)) or (
                "no recognized fitted path"
            )
            equivalent_summary = (
                "none" if equivalent is None else f"{equivalent:g}Ω nominal parallel equivalent"
            )
            unexpected_summary = (
                ""
                if not unexpected_rails
                else "; unexpected direct pull-ups to "
                + ", ".join(
                    sorted(
                        {
                            item.second_net if item.first_net == line.net else item.first_net
                            for item in unexpected_rails
                        }
                    )
                )
            )
            array_failure_summary = (
                ""
                if not array_failures
                else "; mapped resistor-array issue: " + "; ".join(dict.fromkeys(array_failures))
            )
            series_failure_summary = (
                ""
                if not series_failures
                else "; mapped series-path issue: " + "; ".join(dict.fromkeys(series_failures))
            )
            results.append(
                ElectricalCheck(
                    id=f"i2c-pullup/{bus.id}/{name.casefold()}",
                    status="PASS" if passed else "FAIL",
                    observed=equivalent,
                    unit="Ω",
                    detail=(
                        f"{name} net {line.net} to {line.rail}: {path_summary}; "
                        f"{equivalent_summary}; required nominal range "
                        f"{line.minimum_ohms:g}–{line.maximum_ohms:g}Ω"
                        f"{unexpected_summary}{array_failure_summary}{series_failure_summary}."
                    ),
                )
            )
            results.extend(_i2c_pullup_electrical_window_checks(bus.id, name, line))
            if line.voltage_compatibility is not None:
                results.append(
                    _i2c_pullup_voltage_compatibility_check(
                        bus.id,
                        name,
                        line,
                        line.voltage_compatibility,
                        observed,
                    )
                )
    return tuple(results)


def _i2c_pullup_electrical_window_checks(
    bus_id: str, line_name: str, line: I2cPullupLineRequirement
) -> tuple[ElectricalCheck, ...]:
    window = line.electrical_window
    if window is None:
        return ()

    minimum_ohms = (
        (window.maximum_pullup_voltage_v - window.maximum_low_level_voltage_v)
        * 1_000
        / window.minimum_sink_current_ma
    )
    maximum_ohms = (
        window.maximum_rise_time_ns * 1_000 / (0.8473 * window.maximum_bus_capacitance_pf)
    )
    tolerance = window.maximum_per_resistor_tolerance_percent
    tolerance_fraction = 0.0 if tolerance is None else tolerance / 100
    minimum_actual_ohms = line.minimum_ohms * (1 - tolerance_fraction)
    maximum_actual_ohms = line.maximum_ohms * (1 + tolerance_fraction)
    feasible = minimum_ohms < maximum_ohms or math.isclose(
        minimum_ohms, maximum_ohms, rel_tol=1e-12
    )
    empty_detail = (
        " The derived resistor window is empty because its minimum exceeds its maximum."
        if not feasible
        else ""
    )
    minimum_meets_window = minimum_actual_ohms > minimum_ohms or math.isclose(
        minimum_actual_ohms, minimum_ohms, rel_tol=1e-12
    )
    maximum_meets_window = maximum_actual_ohms < maximum_ohms or math.isclose(
        maximum_actual_ohms, maximum_ohms, rel_tol=1e-12
    )
    minimum_status = "PASS" if feasible and minimum_meets_window else "FAIL"
    maximum_status = "PASS" if feasible and maximum_meets_window else "FAIL"
    prefix = f"i2c-pullup/{bus_id}/{line_name.casefold()}/electrical-window"
    minimum_note = (
        ""
        if tolerance is None
        else (
            f"; with the project-authored maximum per-resistor tolerance of {tolerance:g}% "
            f"({window.resistor_tolerance_basis}), the conservative minimum is "
            f"{minimum_actual_ohms:g}Ω"
        )
    )
    maximum_note = (
        ""
        if tolerance is None
        else (
            f"; with the project-authored maximum per-resistor tolerance of {tolerance:g}% "
            f"({window.resistor_tolerance_basis}), the conservative maximum is "
            f"{maximum_actual_ohms:g}Ω"
        )
    )
    return (
        ElectricalCheck(
            id=f"{prefix}/minimum-sink-resistance",
            status=minimum_status,
            observed=(line.minimum_ohms if tolerance is None else minimum_actual_ohms),
            unit="Ω",
            detail=(
                f"The authored {line_name} nominal resistance lower bound to {line.rail} is "
                f"{line.minimum_ohms:g}Ω{minimum_note}; the minimum derived from pull-up rail, low-level "
                f"voltage, and sink-current limits is {minimum_ohms:g}Ω "
                f"(Vpullup,max={window.maximum_pullup_voltage_v:g}V; "
                f"VOL,max={window.maximum_low_level_voltage_v:g}V; "
                f"IOL,min={window.minimum_sink_current_ma:g}mA). Sources: "
                f"{window.pullup_voltage_basis}; {window.low_level_voltage_basis}; "
                f"{window.sink_current_basis}.{empty_detail}"
            ),
        ),
        ElectricalCheck(
            id=f"{prefix}/maximum-rise-resistance",
            status=maximum_status,
            observed=(line.maximum_ohms if tolerance is None else maximum_actual_ohms),
            unit="Ω",
            detail=(
                f"The authored {line_name} nominal resistance upper bound to {line.rail} is "
                f"{line.maximum_ohms:g}Ω{maximum_note}; the maximum derived from the 30%-to-70% RC "
                f"rise-time model is {maximum_ohms:g}Ω "
                f"(tr,max={window.maximum_rise_time_ns:g}ns; "
                f"Cb,max={window.maximum_bus_capacitance_pf:g}pF; "
                "tr=0.8473×Rp×Cb). Sources: "
                f"{window.rise_time_basis}; {window.bus_capacitance_basis}."
                f"{empty_detail}"
            ),
        ),
    )


def _i2c_pullup_voltage_compatibility_check(
    bus_id: str,
    line_name: str,
    line: I2cPullupLineRequirement,
    requirement: I2cPullupVoltageCompatibilityRequirement,
    observed: NetlistContract,
) -> ElectricalCheck:
    """Compare an authored pull-up rail ceiling with exact mapped input limits."""
    components = {
        reference.casefold(): (reference, item) for reference, item in observed.components.items()
    }
    symbols = {
        reference.casefold(): symbol for reference, symbol in observed.component_symbols.items()
    }
    inventories = {
        reference.casefold(): tuple(number.casefold() for number in numbers)
        for reference, numbers in observed.component_pin_numbers.items()
    }
    pin_nets: dict[str, set[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            pin_nets.setdefault(pin.casefold(), set()).add(net)
    dnp = {reference.casefold() for reference in observed.dnp_components}
    issues: list[str] = []

    for input_limit in requirement.input_limits:
        reference, pin_number = input_limit.pin.rsplit(".", 1)
        component = components.get(reference.casefold())
        if component is None:
            issues.append(f"{input_limit.pin} component is absent from the native netlist")
        else:
            actual_reference, details = component
            if actual_reference.casefold() in dnp:
                issues.append(f"{actual_reference} is DNP but is mapped as an active I2C input")
            actual_symbol = symbols.get(reference.casefold())
            if actual_symbol != input_limit.expected_symbol:
                issues.append(
                    f"{reference} symbol is {actual_symbol or '<unknown>'}; "
                    f"expected {input_limit.expected_symbol}"
                )
            if details.footprint != input_limit.expected_footprint:
                issues.append(
                    f"{reference} footprint is {details.footprint or '<empty>'}; "
                    f"expected {input_limit.expected_footprint}"
                )
            native_pin_numbers = inventories.get(reference.casefold())
            if native_pin_numbers is None:
                issues.append(f"{reference} native pin inventory is missing")
            elif pin_number.casefold() not in native_pin_numbers:
                issues.append(
                    f"{input_limit.pin} is absent from the native pin inventory of {reference}"
                )

        actual_nets = pin_nets.get(input_limit.pin.casefold(), set())
        if {net.casefold() for net in actual_nets} != {line.net.casefold()}:
            actual = ", ".join(sorted(actual_nets)) if actual_nets else "unconnected"
            issues.append(f"{input_limit.pin} is assigned to {actual}; expected only {line.net}")
        if requirement.maximum_rail_voltage_v > input_limit.maximum_bus_voltage_v:
            issues.append(
                f"{line.rail} maximum {requirement.maximum_rail_voltage_v:g} V exceeds "
                f"{input_limit.pin} maximum bus voltage {input_limit.maximum_bus_voltage_v:g} V "
                f"({input_limit.limit_kind}; {input_limit.limit_basis})"
            )

    input_summary = "; ".join(
        f"{item.pin} <= {item.maximum_bus_voltage_v:g} V ({item.limit_kind}; {item.limit_basis})"
        for item in requirement.input_limits
    )
    authored_limits = (
        f"reviewed input scope ({requirement.input_scope_basis}); "
        f"{line.rail} maximum {requirement.maximum_rail_voltage_v:g} V "
        f"({requirement.rail_basis}); input limits: {input_summary}"
    )
    return ElectricalCheck(
        id=f"i2c-pullup/{bus_id}/{line_name.casefold()}/voltage-compatibility",
        status="FAIL" if issues else "PASS",
        observed=requirement.maximum_rail_voltage_v,
        unit="V",
        detail=(
            f"{authored_limits}; " + "; ".join(issues)
            if issues
            else (
                f"{authored_limits} is compatible on {line.net}; exact native symbol, footprint, "
                "pin inventory, and net assignments match."
            )
        ),
    )
