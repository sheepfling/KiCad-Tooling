"""Synthetic Ethernet PHY RX status netlists for lint regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def ethernet_rx_status_output_netlist(
    *,
    shared: bool = True,
    references: tuple[str, ...] = ("U1", "U2"),
    status_functions: tuple[str, ...] | None = None,
    status_net_name: str = "MII_RX_DV_SHARED",
    status_type: str = "passive",
    receive_control_functions: tuple[str, ...] | None = None,
    receive_control_shared: bool = True,
    receive_control_net_name: str = "RGMII_RX_CTRL_SHARED",
    receive_control_type: str = "passive",
    dnp_references: tuple[str, ...] = (),
) -> NetlistContract:
    """Build identified PHYs with MII status and optional RGMII RX_CTRL pins."""
    functions = status_functions or tuple("RXDV" for _ in references)
    nets: dict[str, tuple[str, ...]] = {}
    pin_functions: dict[str, str] = {}
    pin_types: dict[str, str] = {}
    inventory: dict[str, tuple[str, ...]] = {}
    receive_control_pins = tuple(f"{reference}.3" for reference in references)
    if shared and len(references) >= 2:
        nets[status_net_name] = tuple(f"{reference}.1" for reference in references)
    if receive_control_functions is not None and receive_control_shared and len(references) >= 2:
        nets[receive_control_net_name] = receive_control_pins
    for index, reference in enumerate(references):
        status_pin = f"{reference}.1"
        data_pin = f"{reference}.2"
        pin_functions[status_pin] = functions[index]
        pin_functions[data_pin] = "RXD0"
        pin_types[status_pin] = status_type
        pin_types[data_pin] = "passive"
        numbers = ["1", "2"]
        if receive_control_functions is not None:
            control_pin = receive_control_pins[index]
            pin_functions[control_pin] = receive_control_functions[index]
            pin_types[control_pin] = receive_control_type
            numbers.append("3")
            if not receive_control_shared:
                nets[f"PHY{index + 1}_RX_CTRL"] = (control_pin,)
        inventory[reference] = tuple(numbers)
        if not shared:
            nets[f"PHY{index + 1}_RX_STATUS"] = (status_pin,)
        nets[f"PHY{index + 1}_RXD0"] = (data_pin,)
    return NetlistContract(
        components={
            reference: ComponentContract(value="LAN8720 Ethernet PHY", footprint="")
            for reference in references
        },
        nets=nets,
        component_symbols={reference: "Synthetic:Ethernet_PHY" for reference in references},
        pin_functions=pin_functions,
        pin_electrical_types=pin_types,
        component_pin_numbers=inventory,
        dnp_components=dnp_references,
    )
