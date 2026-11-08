"""Synthetic source maps and netlists for USB protection-shunt tests."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.usb_data_path_component_models import (
    UsbDataPathInlinePinRequirement,
    UsbDataPathProtectionShuntDataPinRequirement,
    UsbDataPathProtectionShuntRequirement,
)
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
)
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement


def protection_shunt_map(
    *, reference_policy: Literal["common_net", "separate_nets"] | None = None
) -> UsbDataPathMap:
    shunt = UsbDataPathProtectionShuntRequirement(
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
    reference_pins = (
        (UsbReferencePinRequirement(pin="J1.4", net="BOARD_GND"),)
        if reference_policy is not None
        else ()
    )
    phy_reference_pins = (
        (UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),)
        if reference_policy is not None
        else ()
    )
    interface = UsbDataInterfaceRequirement(
        id="usb-port-1",
        basis="Synthetic source-reviewed direct USB path and exact protection pin map",
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
        protection_shunts=(shunt,),
        connector_reference_pins=reference_pins,
        phy_reference_pins=phy_reference_pins,
        reference_policy=reference_policy,
    )
    return UsbDataPathMap(
        basis="Synthetic reviewed USB endpoint and protection-device maps",
        interfaces=(interface,),
    )


def protection_shunt_netlist(*, common_reference: bool = False) -> NetlistContract:
    board_ground_pins = (
        ("J1.4", "U1.3", "U6.2", "U6.4", "U6.5")
        if common_reference
        else ("U1.3", "U6.2", "U6.4", "U6.5")
    )
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-A"),
            "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
            "U6": ComponentContract(
                value="Synthetic protection array", footprint="Synthetic:DFN-6"
            ),
        },
        component_symbols={
            "J1": "Connector:USB_A",
            "U1": "Synthetic:UsbPhy",
            "U6": "Synthetic:UsbProtectionArray",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4"),
            "U6": ("1", "2", "3", "4", "5", "6"),
        },
        nets={
            "USB_DP": ("J1.1", "U1.1", "U6.1"),
            "USB_DM": ("J1.2", "U1.2", "U6.3"),
            **({} if common_reference else {"USB_GND": ("J1.4",)}),
            "BOARD_GND": board_ground_pins,
            "+3V3": ("U1.4",),
        },
        unconnected_nets={"unconnected-(U6-Pad6)": ("U6.6",)},
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "VBUS",
            "J1.4": "GND",
            "U1.1": "USB_DP",
            "U1.2": "USB_DM",
            "U1.3": "AGND",
            "U1.4": "VDD",
            "U6.1": "PORT_DP",
            "U6.2": "GND",
            "U6.3": "PORT_DM",
            "U6.4": "GND",
            "U6.5": "GND",
            "U6.6": "NC",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "U1.1": "bidirectional",
            "U1.2": "bidirectional",
            "U1.3": "power_in",
            "U1.4": "power_in",
            "U6.1": "passive",
            "U6.2": "power_in",
            "U6.3": "passive",
            "U6.4": "power_in",
            "U6.5": "power_in",
            "U6.6": "passive",
        },
    )


def series_protection_shunt_map() -> UsbDataPathMap:
    shunt = UsbDataPathProtectionShuntRequirement(
        reference="U6",
        expected_symbol="Synthetic:UsbProtectionArray",
        expected_footprint="Synthetic:DFN-6",
        data_pins=(
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.1", line="D+", net="USB_DP_PORT"),
            UsbDataPathProtectionShuntDataPinRequirement(pin="U6.3", line="D-", net="USB_DM_PHY"),
        ),
        pins=(
            UsbDataPathInlinePinRequirement(pin="U6.1", disposition="net", net="USB_DP_PORT"),
            UsbDataPathInlinePinRequirement(pin="U6.2", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.3", disposition="net", net="USB_DM_PHY"),
            UsbDataPathInlinePinRequirement(pin="U6.4", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.5", disposition="net", net="BOARD_GND"),
            UsbDataPathInlinePinRequirement(pin="U6.6", disposition="unconnected"),
        ),
    )
    return UsbDataPathMap(
        basis="Synthetic exact USB series-resistor paths with mapped protection taps",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-series-shunt-port-1",
                basis="Synthetic exact two-resistor path and complete protection pin map",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:TUSB2036",
                expected_phy_footprint="Synthetic:QFN",
                positive=UsbDataPathLineRequirement(
                    line="D+",
                    connector_pin="J1.1",
                    phy_pin="U1.1",
                    connector_net="USB_DP_PORT",
                    phy_net="USB_DP_PHY",
                    topology="series_resistor",
                    series_resistor=UsbDataSeriesResistorRequirement(
                        reference="R1",
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:0603",
                        minimum_ohms=27,
                        maximum_ohms=27,
                    ),
                ),
                negative=UsbDataPathLineRequirement(
                    line="D-",
                    connector_pin="J1.2",
                    phy_pin="U1.2",
                    connector_net="USB_DM_PORT",
                    phy_net="USB_DM_PHY",
                    topology="series_resistor",
                    series_resistor=UsbDataSeriesResistorRequirement(
                        reference="R2",
                        expected_symbol="Device:R",
                        expected_footprint="Synthetic:0603",
                        minimum_ohms=27,
                        maximum_ohms=27,
                    ),
                ),
                protection_shunts=(shunt,),
                connector_reference_pins=(UsbReferencePinRequirement(pin="J1.4", net="BOARD_GND"),),
                phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="BOARD_GND"),),
                reference_policy="common_net",
            ),
        ),
    )


def series_protection_shunt_netlist(*, fault: str | None = None) -> NetlistContract:
    observed = protection_shunt_netlist(common_reference=True)
    nets = {
        "USB_DP_PORT": ("J1.1", "R1.1", "U6.1"),
        "USB_DP_PHY": ("R1.2", "U1.1"),
        "USB_DM_PORT": ("J1.2", "R2.1"),
        "USB_DM_PHY": ("R2.2", "U1.2", "U6.3"),
        "BOARD_GND": ("J1.4", "U1.3", "U6.2", "U6.4", "U6.5"),
        "+3V3": ("U1.4",),
    }
    if fault == "wrong-shunt-pin-net":
        nets["BOARD_GND"] = tuple(pin for pin in nets["BOARD_GND"] if pin != "U6.2")
        nets["USB_DP_PORT"] = (*nets["USB_DP_PORT"], "U6.2")
    components = dict(observed.components)
    components.update(
        {
            "R1": ComponentContract(
                value="22R" if fault == "wrong-resistor-value" else "27R",
                footprint="Synthetic:0603",
            ),
            "R2": ComponentContract(value="27R", footprint="Synthetic:0603"),
        }
    )
    return observed.model_copy(
        update={
            "components": components,
            "component_symbols": {
                **observed.component_symbols,
                "U1": "Synthetic:TUSB2036",
                "R1": "Device:R",
                "R2": "Device:R",
            },
            "component_pin_numbers": {
                **observed.component_pin_numbers,
                "R1": ("1", "2"),
                "R2": ("1", "2"),
            },
            "pin_electrical_types": {
                **observed.pin_electrical_types,
                "R1.1": "passive",
                "R1.2": "passive",
                "R2.1": "passive",
                "R2.2": "passive",
            },
            "nets": nets,
        }
    )
