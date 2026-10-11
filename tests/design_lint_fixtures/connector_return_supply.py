"""Synthetic connector return-to-supply cases."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import NetlistContract


def return_pin_positive_rail_netlist(
    *, return_net: str = "+5V", return_function: str = "GND"
) -> NetlistContract:
    """Create one source-only connector with unique signal contacts and one return contact."""
    return NetlistContract(
        components={},
        nets={return_net: ("J1.1",), "TX": ("J1.2",), "RX": ("J1.3",)},
        component_symbols={"J1": "Synthetic:SerialPort"},
        component_pin_numbers={"J1": ("1", "2", "3")},
        pin_functions={"J1.1": return_function, "J1.2": "TX", "J1.3": "RX"},
    )
