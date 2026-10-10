"""Exact synthetic USB path maps used by hosted native fixture lanes."""

from __future__ import annotations

from typing import Literal

from .hwrepo.models import (
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
    UsbReferencePinRequirement,
)
from .hwrepo.reference_bond_models import ReferenceBondRequirement


def usb_data_path_requirements() -> dict[str, UsbDataPathMap]:
    def series_line(
        line: Literal["D+", "D-"], connector_net: str, phy_net: str, resistor: str
    ) -> UsbDataPathLineRequirement:
        return UsbDataPathLineRequirement(
            line=line,
            connector_pin=f"J1.{1 if line == 'D+' else 2}",
            phy_pin=f"U1.{1 if line == 'D+' else 2}",
            connector_net=connector_net,
            phy_net=phy_net,
            topology="series_resistor",
            series_resistor=UsbDataSeriesResistorRequirement(
                reference=resistor,
                expected_symbol="Device:R",
                expected_footprint="Synthetic:0603",
                minimum_ohms=27,
                maximum_ohms=27,
            ),
        )

    series_map = UsbDataPathMap(
        basis="Synthetic source-backed TUSB2036 series-resistor requirement",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="external-usb-phy",
                basis="TI TUSB2036 synthetic fixture requires 27 ohm series resistors",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:TUSB2036",
                expected_phy_footprint="Synthetic:QFN",
                positive=series_line("D+", "USB_D+", "USB_DP_PHY", "R1"),
                negative=series_line("D-", "USB_D-", "USB_DM_PHY", "R2"),
            ),
        ),
    )
    bonded_reference_map = series_map.model_copy(
        update={
            "interfaces": (
                series_map.interfaces[0].model_copy(
                    update={
                        "connector_reference_pins": (
                            UsbReferencePinRequirement(pin="J1.4", net="USB_GND"),
                        ),
                        "phy_reference_pins": (
                            UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),
                        ),
                        "reference_policy": "bonded",
                        "reference_bond": ReferenceBondRequirement(
                            reference="R3",
                            expected_symbol="Device:R",
                            expected_footprint="Synthetic:0603",
                            expected_value="0R",
                            side_a_pin="R3.1",
                            side_b_pin="R3.2",
                            side_a_net="USB_GND",
                            side_b_net="BOARD_GND",
                        ),
                    }
                ),
            )
        }
    )
    direct_map = UsbDataPathMap(
        basis="Synthetic source-backed integrated STM32 full-speed PHY disposition",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="integrated-usb-phy",
                basis="ST AN4879 synthetic fixture selects the integrated direct PHY path",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:STM32F103C8T6",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_D+",
                    phy_net="USB_D+",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_D-",
                    phy_net="USB_D-",
                    topology="direct",
                ),
            ),
        ),
    )
    usb_c_direct_map = UsbDataPathMap(
        basis="Synthetic USB-C duplicate-contact direct-path fixture",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-c-direct-phy",
                basis="Synthetic USB-C D+/D- contacts share direct nets with one integrated PHY",
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbCConnector",
                expected_connector_footprint="Synthetic:USB-C",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.A6",
                    connector_parallel_pins=("J1.B6",),
                    phy_pin="U1.1",
                    connector_net="USB_D+",
                    phy_net="USB_D+",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.A7",
                    connector_parallel_pins=("J1.B7",),
                    phy_pin="U1.2",
                    connector_net="USB_D-",
                    phy_net="USB_D-",
                    topology="direct",
                ),
            ),
        ),
    )
    multiport_map = UsbDataPathMap(
        basis="Synthetic exact mappings for two USB hub ports",
        interfaces=tuple(
            UsbDataInterfaceRequirement(
                id=f"usb-port-{port_group}",
                basis=f"Synthetic exact native path for hub port {port_group}",
                connector_reference=connector,
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbHub",
                expected_phy_footprint="Synthetic:QFN",
                data_port_group=port_group,
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin=f"{connector}.1",
                    phy_pin=f"U1.{positive_pin}",
                    connector_net=f"USB{port_group}_DP",
                    phy_net=f"USB{port_group}_DP",
                    topology="direct",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin=f"{connector}.2",
                    phy_pin=f"U1.{negative_pin}",
                    connector_net=f"USB{port_group}_DM",
                    phy_net=f"USB{port_group}_DM",
                    topology="direct",
                ),
            )
            for connector, port_group, positive_pin, negative_pin in (
                ("J1", "1", "1", "2"),
                ("J2", "2", "4", "5"),
            )
        ),
    )
    requirements = {
        "integrated-direct": direct_map,
        "external-series": series_map,
        "external-series-reference-bond-control": bonded_reference_map,
        "external-series-reference-fault": series_map,
        "external-bypass": series_map,
        "peer-reference-fault": direct_map,
        "peer-reference-control": direct_map,
        "usb-c-peer-reference-fault": usb_c_direct_map,
        "usb-c-peer-reference-control": usb_c_direct_map,
        "usb-multiport-peer-reference-fault": multiport_map,
        "usb-multiport-peer-reference-control": multiport_map,
    }

    return requirements
