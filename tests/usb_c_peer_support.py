"""Synthetic USB-C endpoint and path-map builders."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbReferencePinRequirement,
)


def usb_c_peer_netlist(
    *, connector_reference_net: str = "USB_GND", phy_reference_net: str = "BOARD_GND"
) -> NetlistContract:
    connector_ground_pins = ("J1.A1", "J1.A12", "J1.B1", "J1.B12")
    phy_ground_pins = ("U1.3", "U1.5")
    nets = {
        "USB_DP": ("J1.A6", "J1.B6", "U1.1", "D1.2"),
        "USB_DM": ("J1.A7", "J1.B7", "U1.2", "D2.2"),
        connector_reference_net: (
            *connector_ground_pins,
            "J1.S1",
            "D1.1",
            "D2.1",
        ),
        phy_reference_net: phy_ground_pins,
        "+3V3": ("U1.4",),
    }
    if connector_reference_net.casefold() == phy_reference_net.casefold():
        nets[connector_reference_net] = (
            *connector_ground_pins,
            *phy_ground_pins,
            "J1.S1",
            "D1.1",
            "D2.1",
        )
    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic USB-C receptacle", footprint="Synthetic:USB-C"
            ),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
            "D1": ComponentContract(value="Synthetic TVS branch", footprint="Synthetic:SOD-323"),
            "D2": ComponentContract(value="Synthetic TVS branch", footprint="Synthetic:SOD-323"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector:USB_C",
            "U1": "Synthetic:UsbPhy",
            "D1": "Synthetic:TVS",
            "D2": "Synthetic:TVS",
        },
        pin_functions={
            "J1.A1": "GND",
            "J1.A12": "GND",
            "J1.B1": "GND",
            "J1.B12": "GND",
            "J1.S1": "SHIELD",
            "J1.A6": "D+",
            "J1.B6": "D+",
            "J1.A7": "D-",
            "J1.B7": "D-",
            "U1.1": "D+",
            "U1.2": "D-",
            "U1.3": "AGND",
            "U1.4": "VDD",
            "U1.5": "GND",
            "D1.1": "A",
            "D1.2": "K",
            "D2.1": "A",
            "D2.2": "K",
        },
        pin_electrical_types={
            **{pin: "passive" for pin in connector_ground_pins},
            "J1.S1": "passive",
            "J1.A6": "passive",
            "J1.B6": "passive",
            "J1.A7": "passive",
            "J1.B7": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U1.5": "passive",
            "D1.1": "passive",
            "D1.2": "passive",
            "D2.1": "passive",
            "D2.2": "passive",
        },
        component_pin_numbers={
            "J1": ("A1", "A12", "B1", "B12", "S1", "A6", "B6", "A7", "B7"),
            "U1": ("1", "2", "3", "4", "5"),
            "D1": ("1", "2"),
            "D2": ("1", "2"),
        },
    )


def usb_c_data_map(*, include_duplicate_contacts: bool = True) -> UsbDataPathMap:
    reference_pins = {
        "connector_reference_pins": tuple(
            UsbReferencePinRequirement(pin=pin, net="USB_GND")
            for pin in ("J1.A1", "J1.A12", "J1.B1", "J1.B12")
        ),
        "phy_reference_pins": (
            UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),
            UsbReferencePinRequirement(pin="U1.5", net="BOARD_GND"),
        ),
        "reference_policy": "separate_nets",
    }
    return UsbDataPathMap(
        basis="Synthetic USB-C duplicate-contact reference-domain test",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-c-interface-1",
                basis="Synthetic direct USB-C path with two same-net contacts per data side",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_C",
                expected_connector_footprint="Synthetic:USB-C",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.A6",
                    connector_parallel_pins=("J1.B6",) if include_duplicate_contacts else (),
                    phy_pin="U1.1",
                    connector_net="USB_DP",
                    phy_net="USB_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.A7",
                    connector_parallel_pins=("J1.B7",) if include_duplicate_contacts else (),
                    phy_pin="U1.2",
                    connector_net="USB_DM",
                    phy_net="USB_DM",
                    topology="direct",
                ),
                **reference_pins,
            ),
        ),
    )
