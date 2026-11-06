"""Synthetic generic connector assignments on a USB SuperSpeed PHY pair."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def generic_usb_superspeed_connector_pair_netlist(
    *,
    phy_family: Literal["TX", "RX"] = "TX",
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "GND", "VBUS"),
    include_negative_contact: bool = True,
) -> NetlistContract:
    """Return complete native-like inventories for one direct SS connector pair."""
    positive_net = f"SS_{phy_family}_P"
    negative_net = f"SS_{phy_family}_N"
    positive_pins = ("J1.1", "U1.1")
    negative_pins = ("U1.2", *(("J1.2",) if include_negative_contact else ()))
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        },
        nets={
            positive_net: positive_pins,
            negative_net: negative_pins,
            "USB_GND": ("J1.3", "U1.3"),
            "+3V3": ("U1.4",),
        },
        component_symbols={
            "J1": "Connector_Generic:Conn_01x04",
            "U1": "Synthetic:UsbSuperspeedPhy",
        },
        pin_functions={
            **{f"J1.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": f"SS{phy_family}+",
            "U1.2": f"SS{phy_family}-",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "output" if phy_family == "TX" else "input",
            "U1.2": "output" if phy_family == "TX" else "input",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={"J1": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")},
    )
