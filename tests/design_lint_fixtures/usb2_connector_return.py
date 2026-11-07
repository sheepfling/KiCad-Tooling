"""Synthetic USB 2.0 two-contact connector reference-return fixtures."""

from __future__ import annotations

from kicad_tooling.hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
)


def two_pin_usb2_connector_netlist(
    *,
    connector_functions: tuple[str, str] = ("Pin_1", "Pin_2"),
    connected_return_contact: bool = False,
) -> NetlistContract:
    """Build a native-shaped connector on one exact recognized PHY data pair."""
    pin_numbers = ("1", "2", "3") if connected_return_contact else ("1", "2")
    functions = {
        "J1.1": connector_functions[0],
        "J1.2": connector_functions[1],
        "U1.1": "USB1D+",
        "U1.2": "USB1D-",
        "U1.3": "VSS",
        "U1.4": "VDD",
    }
    electrical_types = {
        "J1.1": "passive",
        "J1.2": "passive",
        "U1.1": "bidirectional",
        "U1.2": "bidirectional",
        "U1.3": "power_in",
        "U1.4": "power_in",
    }
    nets = {
        "USB_DP": ("J1.1", "U1.1"),
        "USB_DM": ("J1.2", "U1.2"),
        "PHY_GND": ("U1.3",),
        "+3V3": ("U1.4",),
    }
    if connected_return_contact:
        functions["J1.3"] = "GND"
        electrical_types["J1.3"] = "passive"
        nets["PHY_GND"] = (*nets["PHY_GND"], "J1.3")

    return NetlistContract(
        components={
            "J1": ComponentContract(
                value="Synthetic USB data connector",
                footprint=f"Synthetic:Conn_01x{len(pin_numbers):02d}",
            ),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        },
        nets=nets,
        component_symbols={
            "J1": f"Connector_Generic:Conn_01x{len(pin_numbers):02d}",
            "U1": "Synthetic:UsbPhy",
        },
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers={"J1": pin_numbers, "U1": ("1", "2", "3", "4")},
    )


def usb2_connector_coverage(
    *,
    not_applicable: bool = False,
    map_return_to_data_contact: bool = False,
) -> ConnectorCoverageReport:
    """Build an exact source-matched two-pin review or disposition map."""
    if not_applicable:
        entry = ConnectorCoverageEntry(reference="J1", status="NOT_APPLICABLE")
    else:
        pins = (
            ConnectorMappedPinEvidence(
                interface_pin_number="GND" if map_return_to_data_contact else "D+",
                interface_signal="GND" if map_return_to_data_contact else "D+",
                component_pin="J1.1",
                role="return" if map_return_to_data_contact else "signal",
                symbol_function="Pin_1",
                nets=("USB_DP",),
            ),
            ConnectorMappedPinEvidence(
                interface_pin_number="D-",
                interface_signal="D-",
                component_pin="J1.2",
                role="signal",
                symbol_function="Pin_2",
                nets=("USB_DM",),
            ),
        )
        entry = ConnectorCoverageEntry(
            reference="J1",
            status="COVERED",
            interface_id="synthetic-usb2",
            basis="Synthetic reviewed USB 2.0 connector pinout",
            interface_pin_map={
                item.interface_pin_number: item.component_pin.rsplit(".", 1)[1] for item in pins
            },
            mapped_pins=pins,
        )
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic USB 2.0 connector inventory",
        inventory_review_basis="Synthetic reviewed connector disposition",
        interface_catalog_sha256="b" * 64,
        entries=(entry,),
    )


def ambiguous_usb2_phy_netlist() -> NetlistContract:
    """Add a second recognized PHY endpoint on the same exact data nets."""
    source = two_pin_usb2_connector_netlist()
    return source.model_copy(
        update={
            "components": {
                **source.components,
                "U2": ComponentContract(
                    value="Second synthetic USB PHY", footprint="Synthetic:QFN"
                ),
            },
            "component_symbols": {**source.component_symbols, "U2": "Synthetic:UsbPhy"},
            "nets": {
                **source.nets,
                "USB_DP": (*source.nets["USB_DP"], "U2.1"),
                "USB_DM": (*source.nets["USB_DM"], "U2.2"),
                "PHY_GND": (*source.nets["PHY_GND"], "U2.3"),
                "+3V3": (*source.nets["+3V3"], "U2.4"),
            },
            "pin_functions": {
                **source.pin_functions,
                "U2.1": "USB1D+",
                "U2.2": "USB1D-",
                "U2.3": "VSS",
                "U2.4": "VDD",
            },
            "pin_electrical_types": {
                **source.pin_electrical_types,
                "U2.1": "bidirectional",
                "U2.2": "bidirectional",
                "U2.3": "power_in",
                "U2.4": "power_in",
            },
            "component_pin_numbers": {**source.component_pin_numbers, "U2": ("1", "2", "3", "4")},
        }
    )


def usb2_data_path_map_without_reference() -> UsbDataPathMap:
    """Map the exact D+/D- data path while leaving reference policy unstated."""
    return UsbDataPathMap(
        basis="Synthetic exact USB 2.0 data path without a reference policy",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="synthetic-j1-usb2-port-1",
                basis="Synthetic USB PHY connector map",
                connector_reference="J1",
                expected_connector_symbol="Connector_Generic:Conn_01x02",
                expected_connector_footprint="Synthetic:Conn_01x02",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                data_port_group="1",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_DP",
                    phy_net="USB_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_DM",
                    phy_net="USB_DM",
                    topology="direct",
                ),
            ),
        ),
    )
