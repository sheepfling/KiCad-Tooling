"""Resolve conservative potential ordering from native rail and pin-role evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from .connector_identity import is_return_function, power_function_key
from .power_rails import explicit_voltage_rail_value
from .return_nets import is_return_like_net_name


@dataclass(frozen=True, slots=True)
class RailPotential:
    """Potential evidence used only to order named component terminals."""

    value: Decimal | None
    positive_symbolic: bool
    return_reference: bool
    evidence: tuple[str, ...]


def named_net_potential(
    net_name: str,
    pins: tuple[str, ...],
    pin_functions: Mapping[str, str],
) -> RailPotential | None:
    """Resolve explicit numeric rails or unambiguous positive/return roles."""
    numeric_values: set[Decimal] = set()
    evidence: set[str] = set()
    positive_symbolic = False
    return_reference = is_return_like_net_name(net_name)
    net_value = explicit_voltage_rail_value(net_name)
    if net_value is not None:
        numeric_values.add(net_value)
        evidence.add(f"explicit net label {net_name} = {net_value} V")
    if power_function_key(net_name) is not None:
        positive_symbolic = True
        evidence.add(f"positive supply net label {net_name}")

    for pin in pins:
        function = pin_functions.get(pin.casefold())
        if function is None:
            continue
        value = explicit_voltage_rail_value(function)
        if value is not None:
            numeric_values.add(value)
            evidence.add(f"pin role {pin}={function} = {value} V")
        if power_function_key(function) is not None:
            positive_symbolic = True
            evidence.add(f"positive supply pin role {pin}={function}")
        if is_return_function(function):
            return_reference = True
            evidence.add(f"return pin role {pin}={function}")

    if len(numeric_values) > 1 or (positive_symbolic and return_reference):
        return None
    if numeric_values:
        value = next(iter(numeric_values))
        if (return_reference and value != 0) or (positive_symbolic and value < 0):
            return None
        if return_reference:
            evidence.add("named return/reference role")
        return RailPotential(
            value=value,
            positive_symbolic=positive_symbolic,
            return_reference=return_reference,
            evidence=tuple(sorted(evidence)),
        )
    if return_reference:
        evidence.add("named return/reference role")
        return RailPotential(
            value=Decimal(0),
            positive_symbolic=False,
            return_reference=True,
            evidence=tuple(sorted(evidence)),
        )
    if positive_symbolic:
        return RailPotential(
            value=None,
            positive_symbolic=True,
            return_reference=False,
            evidence=tuple(sorted(evidence)),
        )
    return None


def potential_is_lower(left: RailPotential, right: RailPotential) -> bool:
    """Compare numeric values or an unambiguous return against a positive role."""
    if left.value is not None and right.value is not None:
        return left.value < right.value
    if left.value is not None and left.value < 0 and right.positive_symbolic:
        return True
    return left.return_reference and right.positive_symbolic
