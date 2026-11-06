"""Synthetic generic connector assignments for USB PHY peer coverage."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


def generic_usb_connector_pair_netlist(
    *,
    connector_functions: tuple[str, ...] = ("Pin_1", "Pin_2", "Pin_3", "Pin_4"),
    include_negative_contact: bool = True,
) -> NetlistContract:
    """Return a complete connector pinout with generic contacts on a USB PHY pair."""
    nets = {
        "+5V": ("J2.1",),
        "USB_DP": ("J2.2", "U1.1"),
        "USB_DM": ("U1.2", *(("J2.3",) if include_negative_contact else ())),
        "BOARD_GND": ("J2.4", "U1.3"),
        "+3V3": ("U1.4",),
    }
    return NetlistContract(
        components={
            "J2": ComponentContract(
                value="Synthetic generic connector", footprint="Synthetic:Conn_01x04"
            ),
            "U1": ComponentContract(value="Synthetic USB hub", footprint="Synthetic:QFN"),
        },
        nets=nets,
        component_symbols={
            "J2": "Connector_Generic:Conn_01x04",
            "U1": "Synthetic:UsbHub",
        },
        pin_functions={
            **{f"J2.{index + 1}": function for index, function in enumerate(connector_functions)},
            "U1.1": "USB1D+",
            "U1.2": "USB1D-",
            "U1.3": "VSS",
            "U1.4": "VDD",
        },
        pin_electrical_types={
            "J2.1": "passive",
            "J2.2": "passive",
            "J2.3": "passive",
            "J2.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
        },
        component_pin_numbers={"J2": ("1", "2", "3", "4"), "U1": ("1", "2", "3", "4")},
    )
