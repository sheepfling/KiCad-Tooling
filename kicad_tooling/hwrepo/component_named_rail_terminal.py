"""Typed native terminal evidence shared by named-rail component reviews."""

from __future__ import annotations

from dataclasses import dataclass

from .component_rail_potentials import RailPotential, named_net_potential
from .netlist_contract_models import NetlistContract
from .netlist_pin_assignments import netlist_pin_net_assignments


def native_pin_function_index(observed: NetlistContract) -> dict[str, str]:
    """Return case-folded pin keys with their exact trimmed native function text."""
    return {
        pin.casefold(): function.strip()
        for pin, function in observed.pin_functions.items()
        if function.strip()
    }


def normalized_pin_function_index(observed: NetlistContract) -> dict[str, str]:
    """Return case-folded pin keys and case-folded native function values."""
    return {
        pin: function.casefold() for pin, function in native_pin_function_index(observed).items()
    }


@dataclass(frozen=True, slots=True)
class NamedRailTerminalEvidence:
    """One exact native terminal assignment and its conservative rail potential."""

    pin: str
    net: str
    potential: RailPotential

    def __post_init__(self) -> None:
        if not self.pin or not self.net:
            raise ValueError("Named-rail terminal evidence requires a pin and net")


def validate_named_rail_terminal(
    observed: NetlistContract,
    terminal: NamedRailTerminalEvidence,
    *,
    expected_pin: str,
) -> None:
    """Require a terminal record to match its current native role, net, and potential."""
    if terminal.pin.casefold() != expected_pin.casefold():
        raise ValueError("Terminal evidence pin must match its current native role")
    assignments = netlist_pin_net_assignments(observed).get(terminal.pin.casefold(), ())
    if assignments != (terminal.net,):
        raise ValueError("Terminal evidence net must match its unique current native assignment")
    pins = observed.nets.get(terminal.net)
    if pins is None:
        raise ValueError("Terminal evidence requires a current native net")
    raw_functions = native_pin_function_index(observed)
    normalized_functions = normalized_pin_function_index(observed)
    # BJT/MOSFET projections use normalized role text; diode/capacitor reports
    # retain the native function spelling in their evidence strings.
    current_potentials = (
        named_net_potential(terminal.net, tuple(pins), raw_functions),
        named_net_potential(terminal.net, tuple(pins), normalized_functions),
    )
    if terminal.potential not in current_potentials:
        raise ValueError("Terminal potential evidence must match the current native net")
