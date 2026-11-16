"""Synthetic RS-485 receiver-output sharing netlists."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def rs485_receiver_output_sharing_netlist(
    *,
    shared: bool = True,
    functions: tuple[str, str] = ("RO", "RO"),
    identities: tuple[str, str] = ("RS-485 transceiver", "RS-485 transceiver"),
    symbol: str = "Synthetic:Rs485_Transceiver",
    pin_type: str = "passive",
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    """Build two explicit fitted RS-485 ICs with complete five-pin inventories."""
    nets = {
        "RX_SHARED": ("U1.4", "U2.4"),
        "U1_A": ("U1.1",),
        "U1_B": ("U1.2",),
        "U1_DI": ("U1.3",),
        "U1_REF": ("U1.5",),
        "U2_A": ("U2.1",),
        "U2_B": ("U2.2",),
        "U2_DI": ("U2.3",),
        "U2_REF": ("U2.5",),
    }
    if not shared:
        nets.pop("RX_SHARED")
        nets.update({"U1_RO": ("U1.4",), "U2_RO": ("U2.4",)})
    return NetlistContract(
        components={
            "U1": ComponentContract(value=identities[0], footprint="Synthetic:IC"),
            "U2": ComponentContract(value=identities[1], footprint="Synthetic:IC"),
        },
        nets=nets,
        dnp_components=dnp,
        component_symbols={"U1": symbol, "U2": symbol},
        pin_functions={
            "U1.1": "A",
            "U1.2": "B",
            "U1.3": "DI",
            "U1.4": functions[0],
            "U1.5": "REF",
            "U2.1": "A",
            "U2.2": "B",
            "U2.3": "DI",
            "U2.4": functions[1],
            "U2.5": "REF",
        },
        pin_electrical_types={"U1.4": pin_type, "U2.4": pin_type},
        component_pin_numbers={"U1": ("1", "2", "3", "4", "5"), "U2": ("1", "2", "3", "4", "5")},
    )
