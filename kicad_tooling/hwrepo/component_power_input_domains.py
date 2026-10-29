"""Review IC supply inputs assigned to separate same-voltage net labels."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .connector_identity import power_function_key
from .models import NetlistContract
from .power_rails import explicit_voltage_rail_value

_IC_REFERENCE = re.compile(r"^(?:U|IC)\d+$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SplitPowerInputDomains:
    reference: str
    symbol: str
    nominal_voltage: str
    pins: dict[str, tuple[str, ...]]


def same_voltage_power_inputs_on_different_nets(
    observed: NetlistContract,
) -> tuple[SplitPowerInputDomains, ...]:
    """Find complete IC power-input inventories split across equal voltage labels.

    This is a review clue only. It does not assert that the domains should be
    joined; filters, ferrite beads, and intentional supply partitions are valid.
    """
    functions = {pin.casefold(): name for pin, name in observed.pin_functions.items()}
    electrical_types = {
        pin.casefold(): kind.casefold() for pin, kind in observed.pin_electrical_types.items()
    }
    symbols = {
        reference.casefold(): (reference, symbol)
        for reference, symbol in observed.component_symbols.items()
    }
    components = {reference.casefold(): reference for reference in observed.components}
    inventories = {
        reference.casefold(): numbers
        for reference, numbers in observed.component_pin_numbers.items()
    }
    assignments: dict[str, list[str]] = {}
    for net, pins in observed.nets.items():
        for pin in pins:
            assignments.setdefault(pin.casefold(), []).append(net)
    dnp = {reference.casefold() for reference in observed.dnp_components}

    findings: list[SplitPowerInputDomains] = []
    for reference_key, reference in sorted(components.items()):
        if (
            not _IC_REFERENCE.fullmatch(reference)
            or reference_key in dnp
            or reference_key not in symbols
        ):
            continue
        pin_numbers = inventories.get(reference_key)
        if not pin_numbers:
            continue
        component_pins = tuple(f"{reference}.{number}" for number in pin_numbers)
        if any(
            pin.casefold() not in functions or pin.casefold() not in electrical_types
            for pin in component_pins
        ):
            continue

        supply_pins: list[tuple[str, str, str, str]] = []
        for pin in component_pins:
            pin_key = pin.casefold()
            function = functions[pin_key]
            function_key = power_function_key(function)
            if function_key is None or electrical_types[pin_key] != "power_in":
                continue
            nets = assignments.get(pin_key, [])
            if len(nets) != 1:
                supply_pins = []
                break
            voltage = explicit_voltage_rail_value(nets[0])
            if voltage is None:
                supply_pins = []
                break
            supply_pins.append((pin, function_key, nets[0], str(voltage)))

        if len(supply_pins) < 2:
            continue
        function_keys = {item[1] for item in supply_pins}
        voltages = {item[3] for item in supply_pins}
        nets = {item[2] for item in supply_pins}
        if len(function_keys) != len(supply_pins) or len(voltages) != 1 or len(nets) < 2:
            continue
        symbol_reference, symbol = symbols[reference_key]
        findings.append(
            SplitPowerInputDomains(
                reference=symbol_reference,
                symbol=symbol,
                nominal_voltage=next(iter(voltages)),
                pins={pin: (net,) for pin, _, net, _ in sorted(supply_pins)},
            )
        )
    return tuple(findings)
