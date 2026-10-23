"""Small synthetic netlists for CAN controller TX/RX same-net checks."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def can_tx_rx_same_net_netlist(
    *,
    shared: bool = True,
    tx_function: str = "CAN1_TX",
    rx_function: str = "CAN1_RX",
    tx_type: str = "output",
    rx_type: str = "input",
    dnp: bool = False,
) -> NetlistContract:
    """Build one synthetic CAN controller with complete native pin inventory."""
    return NetlistContract(
        components={"U1": ComponentContract(value="Synthetic CAN controller", footprint="")},
        nets=(
            {"CAN_CONTROL_SHARED": ("U1.1", "U1.2")}
            if shared
            else {"CAN_TX": ("U1.1",), "CAN_RX": ("U1.2",)}
        ),
        component_symbols={"U1": "Synthetic:CanController"},
        pin_functions={"U1.1": tx_function, "U1.2": rx_function},
        pin_electrical_types={"U1.1": tx_type, "U1.2": rx_type},
        component_pin_numbers={"U1": ("1", "2")},
        dnp_components=("U1",) if dnp else (),
    )
