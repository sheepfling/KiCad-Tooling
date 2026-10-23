"""Synthetic native-netlist inputs for polarized-capacitor polarity review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract

NATIVE_FIXTURE_SHA256 = {
    "fault": "8b87c5640e0ad70a93986a1d10d948f5b71a7ef4bf40ca2c7d2d23db55dfbab1",
    "control": "6defad64c1522c4663706464723f0b241a1900d00f7ddc575841cce11f5f282f",
}


def netlist(
    *,
    positive_terminal_net: str = "-5V",
    negative_terminal_net: str = "+5V",
    positive_peer_function: str | None = None,
    negative_peer_function: str | None = None,
    symbol: str = "Device:C_Polarized",
    inventory: tuple[str, ...] = ("1", "2"),
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build a polarized capacitor with optional rail-role pin evidence."""
    components = {
        "C1": ComponentContract(
            value="Synthetic polarized capacitor",
            footprint="Synthetic:CP_Radial",
        )
    }
    symbols = {"C1": symbol}
    pin_numbers = {"C1": inventory}
    pin_functions = {"C1.1": "~", "C1.2": "~"}
    nets: dict[str, tuple[str, ...]] = {
        positive_terminal_net: ("C1.1",),
        negative_terminal_net: ("C1.2",),
    }
    for reference, net, function in (
        ("U1", positive_terminal_net, positive_peer_function),
        ("U2", negative_terminal_net, negative_peer_function),
    ):
        if function is None:
            continue
        components[reference] = ComponentContract(
            value="Synthetic rail reference",
            footprint="Synthetic:RailReference",
        )
        symbols[reference] = "Synthetic:RailReference"
        pin_numbers[reference] = ("1",)
        pin_functions[f"{reference}.1"] = function
        nets[net] = (*nets[net], f"{reference}.1")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers=pin_numbers,
    )
