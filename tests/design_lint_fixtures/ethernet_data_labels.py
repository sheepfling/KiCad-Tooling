"""Small native-netlist fixtures for Ethernet data-pair label review."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_data_label_netlist(
    functions: tuple[str, str, str, str],
    labels: tuple[str, str, str, str],
    *,
    dnp: bool = False,
) -> NetlistContract:
    """Create one synthetic four-pin Ethernet PHY with explicit pin/net roles."""
    pins = tuple(f"U1.{number}" for number in range(1, 5))
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic Ethernet PHY", footprint="")},
        nets={label: (pin,) for label, pin in zip(labels, pins, strict=True)},
        dnp_components=("U1",) if dnp else (),
        component_symbols={"U1": "Synthetic:EthernetPhy"},
        pin_functions=dict(zip(pins, functions, strict=True)),
        component_pin_numbers={"U1": ("1", "2", "3", "4")},
    )
