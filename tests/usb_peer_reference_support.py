"""Synthetic USB endpoint, path-map, and report builders."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintIgnore,
    DesignLintPolicy,
    DesignLintRuleOverride,
    NetlistContract,
    UsbDataInterfaceRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
    UsbReferencePinRequirement,
)

RULE_ID = "bus.usb_peer_reference_review"
PATH_RULE_ID = "bus.usb_data_path_mismatch"


def usb_peer_netlist(
    *,
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    phy_positive_function: str = "USB_DP",
    phy_negative_function: str = "USB_DM",
    dnp: tuple[str, ...] = (),
    extra_positive_pin: bool = False,
    incomplete: bool = False,
) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic USB-A receptacle", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
    }
    symbols = {"J1": "Connector:USB_A", "U1": "Synthetic:UsbPhy"}
    nets: dict[str, tuple[str, ...]] = {
        "USB_DP": ("J1.1", "U1.1"),
        "USB_DM": ("J1.2", "U1.2"),
        "+3V3": ("U1.4",),
    }
    for reference_net, pin in (
        (connector_reference_net, "J1.3"),
        (phy_reference_net, "U1.3"),
    ):
        nets[reference_net] = (*nets.get(reference_net, ()), pin)
    functions = {
        "J1.1": "D+",
        "J1.2": "D-",
        "J1.3": "GND",
        "J1.4": "VBUS",
        "U1.1": phy_positive_function,
        "U1.2": phy_negative_function,
        "U1.3": "AGND",
        "U1.4": "VDD",
    }
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
    if extra_positive_pin:
        components["TP1"] = ComponentContract(
            value="Synthetic test point", footprint="Synthetic:TestPoint"
        )
        symbols["TP1"] = "Connector:TestPoint"
        nets["USB_DP"] = ("J1.1", "U1.1", "TP1.1")
        functions["TP1.1"] = "TestPoint"
        electrical_types["TP1.1"] = "passive"
    if incomplete:
        electrical_types.pop("U1.3")
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        pin_electrical_types=electrical_types,
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4"),
            **({"TP1": ("1",)} if extra_positive_pin else {}),
        },
    )


def usb_peer_series_netlist(
    *, connector_reference_net: str = "USB_GND", phy_reference_net: str = "BOARD_GND"
) -> NetlistContract:
    base = usb_peer_netlist(
        connector_reference_net=connector_reference_net,
        phy_reference_net=phy_reference_net,
    )

    nets = {name: pins for name, pins in base.nets.items() if name not in {"USB_DP", "USB_DM"}}
    nets.update(
        {
            "USB_DP": ("J1.1", "R1.1"),
            "USB_DP_PHY": ("R1.2", "U1.1"),
            "USB_DM": ("J1.2", "R2.1"),
            "USB_DM_PHY": ("R2.2", "U1.2"),
        }
    )
    components = dict(base.components)
    components.update(
        {
            "R1": ComponentContract(value="27R", footprint="Synthetic:0603"),
            "R2": ComponentContract(value="27R", footprint="Synthetic:0603"),
        }
    )
    symbols = dict(base.component_symbols)
    symbols.update({"R1": "Device:R", "R2": "Device:R"})
    functions = dict(base.pin_functions)
    functions.update({"R1.1": "~", "R1.2": "~", "R2.1": "~", "R2.2": "~"})
    electrical_types = dict(base.pin_electrical_types)
    electrical_types.update(
        {"R1.1": "passive", "R1.2": "passive", "R2.1": "passive", "R2.2": "passive"}
    )
    pin_numbers = dict(base.component_pin_numbers)
    pin_numbers.update({"R1": ("1", "2"), "R2": ("1", "2")})
    return base.model_copy(
        update={
            "components": components,
            "nets": nets,
            "component_symbols": symbols,
            "pin_functions": functions,
            "pin_electrical_types": electrical_types,
            "component_pin_numbers": pin_numbers,
        }
    )


def usb_multiport_peer_netlist(*, common_references: bool = False) -> NetlistContract:
    shared_reference = "BOARD_GND"
    connector_1_reference = shared_reference if common_references else "USB1_GND"
    connector_2_reference = shared_reference if common_references else "USB2_GND"
    phy_reference = shared_reference if common_references else "PHY_GND"
    nets = {
        "USB1_DP": ("J1.1", "U1.1"),
        "USB1_DM": ("J1.2", "U1.2"),
        "USB2_DP": ("J2.1", "U1.4"),
        "USB2_DM": ("J2.2", "U1.5"),
        "+5V": ("J1.4", "J2.4"),
        "+3V3": ("U1.7",),
    }
    for reference_net, pin in (
        (connector_1_reference, "J1.3"),
        (connector_2_reference, "J2.3"),
        (phy_reference, "U1.3"),
        (phy_reference, "U1.6"),
    ):
        nets[reference_net] = (*nets.get(reference_net, ()), pin)
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB-A port 1", footprint="Synthetic:USB-A"),
            "J2": ComponentContract(value="Synthetic USB-A port 2", footprint="Synthetic:USB-A"),
            "U1": ComponentContract(value="Synthetic dual-port USB hub", footprint="Synthetic:QFN"),
        },
        nets=nets,
        component_symbols={
            "J1": "Connector:USB_A",
            "J2": "Connector:USB_A",
            "U1": "Synthetic:UsbHub",
        },
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.3": "GND",
            "J1.4": "VBUS",
            "J2.1": "D+",
            "J2.2": "D-",
            "J2.3": "GND",
            "J2.4": "VBUS",
            "U1.1": "USB1D+",
            "U1.2": "USB1D-",
            "U1.3": "GND",
            "U1.4": "USB2D+",
            "U1.5": "USB2D-",
            "U1.6": "AGND",
            "U1.7": "VDD",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.3": "passive",
            "J1.4": "passive",
            "J2.1": "passive",
            "J2.2": "passive",
            "J2.3": "passive",
            "J2.4": "passive",
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "power_in",
            "U1.4": "input",
            "U1.5": "input",
            "U1.6": "power_in",
            "U1.7": "power_in",
        },
        component_pin_numbers={
            "J1": ("1", "2", "3", "4"),
            "J2": ("1", "2", "3", "4"),
            "U1": ("1", "2", "3", "4", "5", "6", "7"),
        },
    )


def usb_multiport_data_map(*, second_port_group: str = "2") -> UsbDataPathMap:
    def interface(
        connector: str,
        port_group: str,
        connector_reference_net: str,
    ) -> UsbDataInterfaceRequirement:
        phy_positive_pin = "U1.1" if port_group == "1" else "U1.4"
        phy_negative_pin = "U1.2" if port_group == "1" else "U1.5"
        phy_reference_pins = (
            UsbReferencePinRequirement(pin="U1.3", net="PHY_GND"),
            UsbReferencePinRequirement(pin="U1.6", net="PHY_GND"),
        )
        return UsbDataInterfaceRequirement(
            id=f"usb-port-{port_group}",
            basis=f"Synthetic exact USB hub port {port_group} mapping",
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
                phy_pin=phy_positive_pin,
                connector_net=f"USB{port_group}_DP",
                phy_net=f"USB{port_group}_DP",
                topology="direct",
            ),
            negative=UsbDataPathLineRequirement(
                line="D-",
                connector_pin=f"{connector}.2",
                phy_pin=phy_negative_pin,
                connector_net=f"USB{port_group}_DM",
                phy_net=f"USB{port_group}_DM",
                topology="direct",
            ),
            connector_reference_pins=(
                UsbReferencePinRequirement(pin=f"{connector}.3", net=connector_reference_net),
            ),
            phy_reference_pins=phy_reference_pins,
            reference_policy="separate_nets",
        )

    return UsbDataPathMap(
        basis="Synthetic dual-port USB hub mapping",
        interfaces=(
            interface("J1", "1", "USB1_GND"),
            interface("J2", second_port_group, "USB2_GND"),
        ),
    )


def usb_series_data_map(
    *,
    reference_policy: str | None = "separate_nets",
    connector_reference_net: str = "USB_GND",
    phy_reference_net: str = "BOARD_GND",
    positive_resistor: str = "R1",
    negative_resistor: str = "R2",
) -> UsbDataPathMap:
    reference_pins: dict[str, object] = {}
    if reference_policy is not None:
        reference_pins = {
            "connector_reference_pins": (
                UsbReferencePinRequirement(pin="J1.3", net=connector_reference_net),
            ),
            "phy_reference_pins": (UsbReferencePinRequirement(pin="U1.3", net=phy_reference_net),),
            "reference_policy": reference_policy,
        }

    def line_requirement(
        line: Literal["D+", "D-"],
        connector_net: str,
        phy_net: str,
        resistor: str,
        connector_pin: str,
        phy_pin: str,
    ) -> UsbDataPathLineRequirement:
        return UsbDataPathLineRequirement(
            line=line,
            connector_pin=connector_pin,
            phy_pin=phy_pin,
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

    return UsbDataPathMap(
        basis="Synthetic USB series-resistor peer reference test",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-series-interface-1",
                basis="Synthetic USB pair with one fitted series resistor on each data line",
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol="Synthetic:UsbPhy",
                expected_phy_footprint="Synthetic:QFN",
                positive=line_requirement(
                    "D+", "USB_DP", "USB_DP_PHY", positive_resistor, "J1.1", "U1.1"
                ),
                negative=line_requirement(
                    "D-", "USB_DM", "USB_DM_PHY", negative_resistor, "J1.2", "U1.2"
                ),
                **reference_pins,
            ),
        ),
    )


def usb_data_map(
    *,
    reference_policy: str | None = None,
    expected_connector_reference_net: str = "USB_GND",
    expected_phy_reference_net: str = "BOARD_GND",
    phy_reference_pin: str = "U1.3",
) -> UsbDataPathMap:
    reference_pins: dict[str, object] = {}
    if reference_policy is not None:
        reference_pins = {
            "connector_reference_pins": (
                UsbReferencePinRequirement(pin="J1.3", net=expected_connector_reference_net),
            ),
            "phy_reference_pins": (
                UsbReferencePinRequirement(
                    pin=phy_reference_pin,
                    net=expected_phy_reference_net,
                ),
            ),
            "reference_policy": reference_policy,
        }
    return UsbDataPathMap(
        basis="Synthetic USB peer and explicit endpoint-reference review",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-interface-1",
                basis="Synthetic direct integrated USB PHY path",
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
                **reference_pins,
            ),
        ),
    )


def lint_report(
    observed: NetlistContract,
    *,
    path_map: UsbDataPathMap | None = None,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-peer-reference",
        observed=observed,
        netlist_sha256="b" * 64,
    )
    return evaluate(
        "synthetic-usb-peer-reference",
        coach,
        DesignLintPolicy(
            usb_data_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )
