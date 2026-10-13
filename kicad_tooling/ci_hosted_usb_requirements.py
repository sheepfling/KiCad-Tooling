"""Exact synthetic USB path maps used by hosted native fixture lanes."""

from __future__ import annotations

from typing import Literal

from .hwrepo.reference_bond_models import ReferenceBondRequirement
from .hwrepo.usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from .hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathInlineComponentRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
)
from .hwrepo.usb_reference_pin_models import UsbReferencePinRequirement


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
    isolator_map = multiport_map.model_copy(
        update={
            "basis": "Synthetic exact mappings for two isolated USB ports",
            "interfaces": tuple(
                item.model_copy(
                    update={
                        "basis": f"Synthetic exact native path for isolated port {item.data_port_group}",
                        "expected_phy_symbol": "Synthetic:UsbIsolator",
                    }
                )
                for item in multiport_map.interfaces
            ),
        }
    )
    inline_component_map = UsbDataPathMap(
        basis="Synthetic exact USB multi-pin pass-through component map",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-protected-port-1",
                basis="Synthetic reviewed USB protection pin-to-net requirement",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_DP_PORT",
                    phy_net="USB_DP_PHY",
                    topology="inline_component",
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_DM_PORT",
                    phy_net="USB_DM_PHY",
                    topology="inline_component",
                ),
                inline_component=UsbDataPathInlineComponentRequirement(
                    reference="U2",
                    expected_symbol="Synthetic:UsbProtection",
                    expected_footprint="Synthetic:QFN",
                    positive_connector_pin="U2.1",
                    positive_phy_pin="U2.2",
                    negative_connector_pin="U2.3",
                    negative_phy_pin="U2.4",
                    pins=(
                        UsbDataPathInlinePinRequirement(
                            pin="U2.1", disposition="net", net="USB_DP_PORT"
                        ),
                        UsbDataPathInlinePinRequirement(
                            pin="U2.2", disposition="net", net="USB_DP_PHY"
                        ),
                        UsbDataPathInlinePinRequirement(
                            pin="U2.3", disposition="net", net="USB_DM_PORT"
                        ),
                        UsbDataPathInlinePinRequirement(
                            pin="U2.4", disposition="net", net="USB_DM_PHY"
                        ),
                        UsbDataPathInlinePinRequirement(pin="U2.5", disposition="net", net="GND"),
                        UsbDataPathInlinePinRequirement(pin="U2.6", disposition="unconnected"),
                    ),
                ),
                connector_reference_pins=(UsbReferencePinRequirement(pin="J1.4", net="GND"),),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="GND"),),
                reference_policy="common_net",
            ),
        ),
    )
    inline_component_interface = inline_component_map.interfaces[0]
    inline_component_requirement = inline_component_interface.inline_component
    assert inline_component_requirement is not None
    split_inline_pin_map = inline_component_requirement.model_copy(
        update={
            "pins": tuple(
                item.model_copy(update={"net": "BOARD_GND"})
                if item.pin.casefold() == "u2.5"
                else item
                for item in inline_component_requirement.pins
            )
        }
    )
    inline_peer_fault = inline_component_interface.model_copy(
        update={
            "inline_component": split_inline_pin_map,
            "connector_reference_pins": (),
            "phy_reference_pins": (),
            "reference_policy": None,
        }
    )
    inline_peer_map_control = inline_component_interface.model_copy(
        update={
            "inline_component": split_inline_pin_map,
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.4", net="USB_GND"),),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
            "reference_policy": "separate_nets",
        }
    )
    inline_peer_bond_control = inline_component_interface.model_copy(
        update={
            "inline_component": split_inline_pin_map,
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.4", net="USB_GND"),),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
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
    )
    inline_component_peer_fault_map = UsbDataPathMap(
        basis="Synthetic exact USB inline path without a reference disposition",
        interfaces=(inline_peer_fault,),
    )
    inline_component_peer_control_map = UsbDataPathMap(
        basis="Synthetic exact USB inline path with reviewed separate references",
        interfaces=(inline_peer_map_control,),
    )
    inline_component_peer_bond_control_map = UsbDataPathMap(
        basis="Synthetic exact USB inline path with a mapped fitted reference bond",
        interfaces=(inline_peer_bond_control,),
    )

    protection_shunt = UsbDataPathProtectionShuntRequirement(
        reference="U6",
        expected_symbol="Synthetic:UsbProtectionArray",
        expected_footprint="Synthetic:DFN-6",
        data_pins=(
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.1", line="D+", net="USB_DP"),
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.3", line="D-", net="USB_DM"),
        ),
        pins=(
            UsbDataPathInlinePinRequirement(pin="U6.1", disposition="net", net="USB_DP"),
            UsbDataPathInlinePinRequirement(pin="U6.2", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.3", disposition="net", net="USB_DM"),
            UsbDataPathInlinePinRequirement(pin="U6.4", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.5", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.6", disposition="unconnected"),
        ),
    )

    def protection_shunt_map(*, common_reference: bool) -> UsbDataPathMap:
        return UsbDataPathMap(
            basis="Synthetic exact USB protection-shunt pin map",
            interfaces=(
                UsbDataInterfaceRequirement(
                    id="usb-protection-shunt-port-1",
                    basis="Synthetic reviewed direct USB pair and protection shunt",
                    connector_reference="J1",
                    expected_connector_symbol="Connector:USB_A",
                    expected_connector_footprint="Synthetic:USB-A",
                    phy_reference="U1",
                    expected_phy_symbol="Synthetic:UsbPhy",
                    expected_phy_footprint="Synthetic:QFN",
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
                    protection_shunts=(protection_shunt,),
                    connector_reference_pins=(
                        (UsbReferencePinRequirement(pin="J1.4", net="BOARD_GND"),)
                        if common_reference
                        else ()
                    ),
                    phy_reference_pins=(
                        (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),)
                        if common_reference
                        else ()
                    ),
                    reference_policy="common_net" if common_reference else None,
                ),
            ),
        )

    protection_shunt_split_map = protection_shunt_map(common_reference=False)
    protection_shunt_common_map = protection_shunt_map(common_reference=True)
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
        "intentional-isolation-boundary": isolator_map,
        "inline-component-control": inline_component_map,
        "inline-component-ground-fault": inline_component_map,
        "inline-component-peer-reference-fault": inline_component_peer_fault_map,
        "inline-component-peer-reference-map-control": inline_component_peer_control_map,
        "inline-component-peer-reference-bond-fault": inline_component_peer_bond_control_map,
        "inline-component-peer-reference-bond-control": inline_component_peer_bond_control_map,
        "protection-shunt-split-reference": protection_shunt_split_map,
        "protection-shunt-common-reference": protection_shunt_common_map,
        "protection-shunt-pin-fault": protection_shunt_split_map,
    }

    return requirements
