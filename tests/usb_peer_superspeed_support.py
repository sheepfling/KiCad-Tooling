"""Synthetic USB SuperSpeed peer inputs for focused verification cases."""

from __future__ import annotations

from kicad_tooling.hwrepo.models import ComponentContract, NetlistContract


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
    return NetlistContract(
        components=components,
        nets={
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
        },
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers=inventories,
    )
