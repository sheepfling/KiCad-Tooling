"""Synthetic USB SuperSpeed peer inputs for focused verification cases."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract
from kicad_tooling.hwrepo.reference_bond_models import ReferenceBondRequirement
from kicad_tooling.hwrepo.usb_data_path_models import UsbDataPathMap
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement
from kicad_tooling.hwrepo.usb_superspeed_reference_models import (
    UsbSuperspeedReferencePathRequirement,
)


def superspeed_peer_netlist(
    *,
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    phy_pair_family: str = "SSRX",
    extra_positive_peer: bool = False,
    missing_metadata_pin: str | None = None,
    dnp: tuple[str, ...] = (),
    reverse_polarity: bool = False,
    full_duplex: bool = False,
    bond_value: str | None = None,
) -> NetlistContract:
    """Build one direct connector-TX-to-PHY-RX pair with complete pin metadata."""
    positive_phy_pin = "U1.2" if reverse_polarity else "U1.1"
    negative_phy_pin = "U1.1" if reverse_polarity else "U1.2"
    positive_net_pins = ("J1.1", positive_phy_pin)
    if extra_positive_peer:
        positive_net_pins = (*positive_net_pins, "TP1.1")
    components = {
        "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
    }
    symbols = {"J1": "Connector:USB_A", "U1": "Synthetic:UsbPhy"}
    pins = ("1", "2", "3", "4", "5", "6") if full_duplex else ("1", "2", "3", "4")
    inventories = {"J1": pins, "U1": pins}
    functions = {
        "J1.1": "StdA SSTX+",
        "J1.2": "StdA SSTX-",
        "J1.3": "GND",
        "J1.4": "VBUS",
        "U1.1": f"{phy_pair_family}+",
        "U1.2": f"{phy_pair_family}-",
        "U1.3": "AGND",
        "U1.4": "VDD",
    }
    if full_duplex:
        functions.update(
            {
                "J1.5": "SSRX+",
                "J1.6": "SSRX-",
                "U1.5": "SSTX+",
                "U1.6": "SSTX-",
            }
        )
    electrical_types = {
        "J1.1": "passive",
        "J1.2": "passive",
        "J1.3": "passive",
        "J1.4": "passive",
        "U1.1": "bidirectional",
        "U1.2": "bidirectional",
        "U1.3": "power_in",
        "U1.4": "power_in",
    }
    if full_duplex:
        electrical_types.update(
            {
                "J1.5": "passive",
                "J1.6": "passive",
                "U1.5": "bidirectional",
                "U1.6": "bidirectional",
            }
        )
    if extra_positive_peer:
        components["TP1"] = ComponentContract(
            value="Synthetic test point", footprint="Synthetic:TestPoint"
        )
        symbols["TP1"] = "Connector:TestPoint"
        inventories["TP1"] = ("1",)
        functions["TP1.1"] = "TestPoint"
        electrical_types["TP1.1"] = "passive"
    if missing_metadata_pin is not None:
        electrical_types.pop(missing_metadata_pin)
    reference_nets: dict[str, tuple[str, ...]] = {}
    reference_nets[connector_reference_net] = ("J1.3",)
    reference_nets[phy_reference_net] = (
        *reference_nets.get(phy_reference_net, ()),
        "U1.3",
    )
    nets = {
        **reference_nets,
        "SS_LANE_A": positive_net_pins,
        "SS_LANE_B": ("J1.2", negative_phy_pin),
        "+5V": ("J1.4",),
        "+3V3": ("U1.4",),
        **(
            {
                "SS_LANE_C": ("J1.5", "U1.5"),
                "SS_LANE_D": ("J1.6", "U1.6"),
            }
            if full_duplex
            else {}
        ),
    }
    component_pin_numbers = dict(inventories)
    if bond_value is not None:
        components["R3"] = ComponentContract(value=bond_value, footprint="Synthetic:0603")
        symbols["R3"] = "Device:R"
        component_pin_numbers["R3"] = ("1", "2")
        nets[connector_reference_net] = (*nets[connector_reference_net], "R3.1")
        nets[phy_reference_net] = (*nets[phy_reference_net], "R3.2")
        electrical_types["R3.1"] = "passive"
        electrical_types["R3.2"] = "passive"

    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers=component_pin_numbers,
    )


def superspeed_reference_map(
    *,
    policy: Literal["common_net", "separate_nets", "bonded"] = "separate_nets",
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    full_duplex: bool = False,
    reference_bond: ReferenceBondRequirement | None = None,
) -> UsbDataPathMap:
    """Build reviewed exact SuperSpeed paths for synthetic regression tests."""
    pairs = [
        (
            "ss-tx-to-rx",
            "USB SuperSpeed TX",
            "USB SuperSpeed RX",
            "J1.1",
            "U1.1",
            "J1.2",
            "U1.2",
            "SS_LANE_A",
            "SS_LANE_B",
        )
    ]
    if full_duplex:
        pairs.append(
            (
                "ss-rx-to-tx",
                "USB SuperSpeed RX",
                "USB SuperSpeed TX",
                "J1.5",
                "U1.5",
                "J1.6",
                "U1.6",
                "SS_LANE_C",
                "SS_LANE_D",
            )
        )
    interfaces = tuple(
        UsbSuperspeedReferencePathRequirement(
            id=interface_id,
            basis="Synthetic reviewer-approved USB SuperSpeed endpoint and return map",
            connector_reference="J1",
            expected_connector_symbol="Connector:USB_A",
            expected_connector_footprint="Synthetic:USB-A",
            phy_reference="U1",
            expected_phy_symbol="Synthetic:UsbPhy",
            expected_phy_footprint="Synthetic:QFN",
            connector_signal_family=connector_family,
            phy_signal_family=phy_family,
            connector_positive_pin=connector_positive,
            phy_positive_pin=phy_positive,
            positive_net=positive_net,
            connector_negative_pin=connector_negative,
            phy_negative_pin=phy_negative,
            negative_net=negative_net,
            connector_reference_pins=(
                UsbReferencePinRequirement(pin="J1.3", net=connector_reference_net),
            ),
            phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net=phy_reference_net),),
            reference_policy=policy,
            reference_bond=reference_bond,
        )
        for (
            interface_id,
            connector_family,
            phy_family,
            connector_positive,
            phy_positive,
            connector_negative,
            phy_negative,
            positive_net,
            negative_net,
        ) in pairs
    )
    return UsbDataPathMap(
        basis="Synthetic project-approved USB SuperSpeed reference map",
        superspeed_interfaces=interfaces,
    )


def superspeed_reference_bond() -> ReferenceBondRequirement:
    return ReferenceBondRequirement(
        reference="R3",
        expected_symbol="Device:R",
        expected_footprint="Synthetic:0603",
        expected_value="0R",
        side_a_pin="R3.1",
        side_b_pin="R3.2",
        side_a_net="USB_GND",
        side_b_net="BOARD_GND",
    )
