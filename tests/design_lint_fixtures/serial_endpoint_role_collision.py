"""Synthetic UART connector and controller endpoint-role assignments."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def serial_endpoint_role_netlist(
    *,
    collision: bool = True,
    dnp: tuple[str, ...] = (),
    incomplete_connector_inventory: bool = False,
    ambiguous_assignment: bool = False,
    extra_net_pin: bool = False,
    output_conflict: bool = False,
) -> NetlistContract:
    """Build same-role UART connector/IC faults and crossed TX/RX controls."""
    functions = {
        "J1.1": "UART1_TX",
        "J1.2": "UART1_RX",
        "U1.1": "UART1_TX",
        "U1.2": "UART1_RX",
    }
    if collision:
        nets = {
            "UART_TX": ("J1.1", "U1.1"),
            "UART_RX": ("J1.2", "U1.2"),
        }
    else:
        functions["J1.1"], functions["J1.2"] = "UART1_TX", "UART1_RX"
        nets = {
            "UART_TX": ("J1.1", "U1.2"),
            "UART_RX": ("J1.2", "U1.1"),
        }
    types = {
        "J1.1": "output" if output_conflict else "input",
        "J1.2": "output",
        "U1.1": "output",
        "U1.2": "output" if output_conflict else "input",
    }
    if ambiguous_assignment:
        nets["UART_OTHER"] = ("J1.1",)
    if extra_net_pin:
        nets["UART_TX"] = (*nets["UART_TX"], "R1.1")
        components = {
            "J1": ComponentContract(value="Synthetic UART header", footprint="Synthetic:Header"),
            "U1": ComponentContract(value="Synthetic UART controller", footprint="Synthetic:IC"),
            "R1": ComponentContract(value="Synthetic test point", footprint="Synthetic:Test"),
        }
        functions["R1.1"] = "UART1_TX"
        types["R1.1"] = "passive"
        inventory = {"J1": ("1", "2"), "U1": ("1", "2"), "R1": ("1",)}
    else:
        components = {
            "J1": ComponentContract(value="Synthetic UART header", footprint="Synthetic:Header"),
            "U1": ComponentContract(value="Synthetic UART controller", footprint="Synthetic:IC"),
        }
        inventory = {"J1": ("1", "2"), "U1": ("1", "2")}
    if incomplete_connector_inventory:
        inventory["J1"] = ("1",)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols={"J1": "Connector:Serial_Header", "U1": "Synthetic:UartController"},
        pin_functions=functions,
        pin_electrical_types=types,
        component_pin_numbers=inventory,
        dnp_components=dnp,
    )
