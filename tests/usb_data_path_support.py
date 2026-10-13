"""Synthetic USB data-path project builders shared by focused regression suites."""

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
    ReferenceBondRequirement,
)
from kicad_tooling.hwrepo.usb_data_path_component_models import UsbDataPathInlinePinRequirement
from kicad_tooling.hwrepo.usb_data_path_models import (
    UsbDataInterfaceRequirement,
    UsbDataPathInlineComponentRequirement,
    UsbDataPathLineRequirement,
    UsbDataPathMap,
    UsbDataSeriesResistorRequirement,
)
from kicad_tooling.hwrepo.usb_reference_pin_models import UsbReferencePinRequirement


def usb_data_map(
    topology: Literal["direct", "series_resistor"] = "series_resistor",
) -> UsbDataPathMap:
    if topology == "direct":
        positive = UsbDataPathLineRequirement(
            line="D+",
            connector_pin="J1.1",
            phy_pin="U1.1",
            connector_net="USB_DP",
            phy_net="USB_DP",
            topology="direct",
        )
        negative = UsbDataPathLineRequirement(
            line="D-",
            connector_pin="J1.2",
            phy_pin="U1.2",
            connector_net="USB_DM",
            phy_net="USB_DM",
            topology="direct",
        )
        phy_symbol = "Synthetic:STM32F103"
        basis = (
            "STMicroelectronics AN4879 Rev 12, FAQ: the internal FS PHY includes output "
            "matching impedance; this project selects a direct schematic path."
        )
    else:
        positive = UsbDataPathLineRequirement(
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
        )
        negative = UsbDataPathLineRequirement(
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
        )
        phy_symbol = "Synthetic:TUSB2036"
        basis = (
            "TI TUSB2036 datasheet Rev I, Section 9.2: approximately 27 ohm series "
            "resistors are required on USB DP/DM pairs; this project selects 27R."
        )
    return UsbDataPathMap(
        basis="Synthetic project-approved USB data interface disposition",
        interfaces=(
            UsbDataInterfaceRequirement(
                id="usb-port-1",
                basis=basis,
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbA",
                expected_connector_footprint="Synthetic:USB-A",
                phy_reference="U1",
                expected_phy_symbol=phy_symbol,
                expected_phy_footprint="Synthetic:QFN",
                positive=positive,
                negative=negative,
            ),
        ),
    )


def usb_bonded_reference_map() -> UsbDataPathMap:
    base = usb_data_map()
    interface = base.interfaces[0].model_copy(
        update={
            "connector_reference_pins": (UsbReferencePinRequirement(pin="J1.3", net="USB_GND"),),
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
    return base.model_copy(update={"interfaces": (interface,)})


def usb_inline_component_map() -> UsbDataPathMap:
    inline = UsbDataPathInlineComponentRequirement(
        reference="U2",
        expected_symbol="Synthetic:UsbProtection",
        expected_footprint="Synthetic:QFN",
        positive_connector_pin="U2.1",
        positive_phy_pin="U2.2",
        negative_connector_pin="U2.3",
        negative_phy_pin="U2.4",
        pins=(
            UsbDataPathInlinePinRequirement(pin="U2.1", disposition="net", net="USB_DP_PORT"),
            UsbDataPathInlinePinRequirement(pin="U2.2", disposition="net", net="USB_DP_PHY"),
            UsbDataPathInlinePinRequirement(pin="U2.3", disposition="net", net="USB_DM_PORT"),
            UsbDataPathInlinePinRequirement(pin="U2.4", disposition="net", net="USB_DM_PHY"),
            UsbDataPathInlinePinRequirement(pin="U2.5", disposition="net", net="GND"),
            UsbDataPathInlinePinRequirement(pin="U2.6", disposition="unconnected"),
        ),
    )
    interface = UsbDataInterfaceRequirement(
        id="usb-protected-port-1",
        basis="Synthetic reviewed multi-pin pass-through component pin map",
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
        inline_component=inline,
        connector_reference_pins=(UsbReferencePinRequirement(pin="J1.4", net="GND"),),
        phy_reference_pins=(UsbReferencePinRequirement(pin="U1.3", net="GND"),),
        reference_policy="common_net",
    )
    return UsbDataPathMap(
        basis="Synthetic project-authored USB protection path map",
        interfaces=(interface,),
    )


def usb_inline_component_netlist(*, fault: str | None = None) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(value="Synthetic USB PHY", footprint="Synthetic:QFN"),
        "U2": ComponentContract(value="Synthetic USB protection", footprint="Synthetic:QFN"),
    }
    symbols = {
        "J1": "Connector:USB_A",
        "U1": "Synthetic:UsbPhy",
        "U2": "Synthetic:UsbProtection",
    }
    pin_numbers = {
        "J1": ("1", "2", "4"),
        "U1": ("1", "2", "3"),
        "U2": ("1", "2", "3", "4", "5", "6"),
    }
    nets: dict[str, tuple[str, ...]] = {
        "USB_DP_PORT": ("J1.1", "U2.1"),
        "USB_DP_PHY": ("U2.2", "U1.1"),
        "USB_DM_PORT": ("J1.2", "U2.3"),
        "USB_DM_PHY": ("U2.4", "U1.2"),
        "GND": ("J1.4", "U1.3", "U2.5"),
    }
    unconnected_nets = {"NC": ("U2.6",)}
    dnp_components: tuple[str, ...] = ()
    if fault == "missing-component":
        components.pop("U2")
        symbols.pop("U2")
        pin_numbers.pop("U2")
        for net, pins in tuple(nets.items()):
            nets[net] = tuple(pin for pin in pins if not pin.startswith("U2."))
    elif fault == "wrong-positive-input-net":
        nets["USB_DP_PORT"] = ("J1.1",)
        nets["OTHER"] = ("U2.1",)
    elif fault == "wrong-reference-net":
        nets["GND"] = ("J1.4", "U1.3")
        nets["FLOATING_GND"] = ("U2.5",)
    elif fault == "extra-native-pin":
        pin_numbers["U2"] = (*pin_numbers["U2"], "7")
    elif fault == "connected-optional-pin":
        unconnected_nets = {}
        nets["VBUS"] = ("U2.6",)
    elif fault == "unmarked-optional-pin":
        unconnected_nets = {}
    elif fault == "wrong-symbol":
        symbols["U2"] = "Synthetic:WrongProtection"
    elif fault == "wrong-footprint":
        components["U2"] = ComponentContract(
            value="Synthetic USB protection", footprint="Synthetic:DFN"
        )
    elif fault == "dnp":
        dnp_components = ("U2",)

    return NetlistContract(
        components=components,
        nets=nets,
        unconnected_nets=unconnected_nets,
        dnp_components=dnp_components,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "J1.4": "GND",
            "U1.1": "DP1",
            "U1.2": "DM1",
            "U1.3": "AGND",
        },
        pin_electrical_types={
            "J1.1": "passive",
            "J1.2": "passive",
            "J1.4": "passive",
            "U1.1": "input",
            "U1.2": "input",
            "U1.3": "power_in",
        },
    )


def usb_netlist(
    topology: Literal["direct", "series_resistor"] = "series_resistor",
    *,
    fault: str | None = None,
) -> NetlistContract:
    components = {
        "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-A"),
        "U1": ComponentContract(
            value="STM32F103C8T6" if topology == "direct" else "TUSB2036",
            footprint="Synthetic:QFN",
        ),
    }
    symbols = {
        "J1": "Synthetic:UsbA",
        "U1": "Synthetic:STM32F103" if topology == "direct" else "Synthetic:TUSB2036",
    }
    pin_numbers = {"J1": ("1", "2"), "U1": ("1", "2")}
    if topology == "direct":
        nets: dict[str, tuple[str, ...]] = {
            "USB_DP": ("J1.1", "U1.1"),
            "USB_DM": ("J1.2", "U1.2"),
        }
    else:
        components.update(
            {
                "R1": ComponentContract(value="27R", footprint="Synthetic:0603"),
                "R2": ComponentContract(value="27R", footprint="Synthetic:0603"),
            }
        )
        symbols.update({"R1": "Device:R", "R2": "Device:R"})
        pin_numbers.update({"R1": ("1", "2"), "R2": ("1", "2")})
        nets = {
            "USB_DP_PORT": ("J1.1", "R1.1"),
            "USB_DP_PHY": ("R1.2", "U1.1"),
            "USB_DM_PORT": ("J1.2", "R2.1"),
            "USB_DM_PHY": ("R2.2", "U1.2"),
        }
        if fault == "missing-dp-resistor":
            components.pop("R1")
            symbols.pop("R1")
            pin_numbers.pop("R1")
            nets["USB_DP_PORT"] = ("J1.1",)
            nets["USB_DP_PHY"] = ("U1.1",)
        elif fault == "wrong-dp-resistor-value":
            components["R1"] = ComponentContract(value="22R", footprint="Synthetic:0603")
        elif fault == "dnp-dp-resistor":
            return NetlistContract(
                components=components,
                nets=nets,
                dnp_components=("R1",),
                component_symbols=symbols,
                component_pin_numbers=pin_numbers,
                pin_functions={"J1.1": "D+", "J1.2": "D-"},
            )
        elif fault == "wrong-dp-resistor-net":
            nets["USB_DP_PHY"] = ("U1.1",)
            nets["OTHER"] = ("R1.2",)
    return NetlistContract(
        components=components,
        nets=nets,
        component_symbols=symbols,
        component_pin_numbers=pin_numbers,
        pin_functions={
            "J1.1": "D+",
            "J1.2": "D-",
            "U1.1": "DP1" if topology == "series_resistor" else "USB_DP",
            "U1.2": "DM1" if topology == "series_resistor" else "USB_DM",
        },
    )


def usb_bonded_reference_netlist(*, fault: str | None = None) -> NetlistContract:
    base = usb_netlist()
    components = dict(base.components)
    symbols = dict(base.component_symbols)
    pins = dict(base.component_pin_numbers)
    functions = dict(base.pin_functions)
    electrical_types = dict(base.pin_electrical_types)
    nets = dict(base.nets)
    dnp: tuple[str, ...] = ()
    if fault != "missing":
        components["R3"] = ComponentContract(value="0R", footprint="Synthetic:0603")
        symbols["R3"] = "Device:R"
        pins["R3"] = ("1", "2")
        functions.update({"R3.1": "~", "R3.2": "~"})
        electrical_types.update({"R3.1": "passive", "R3.2": "passive"})
        if fault == "wrong-value":
            components["R3"] = ComponentContract(value="10R", footprint="Synthetic:0603")
        elif fault == "wrong-symbol":
            symbols["R3"] = "Synthetic:Bond"
        elif fault == "wrong-footprint":
            components["R3"] = ComponentContract(value="0R", footprint="Synthetic:0805")
        elif fault == "active-pin":
            electrical_types["R3.2"] = "input"
        elif fault == "DNP":
            dnp = ("R3",)
    nets["USB_GND"] = ("J1.3", "R3.1") if fault != "missing" else ("J1.3",)
    nets["BOARD_GND"] = ("U1.3",)
    if fault == "wrong-net":
        nets["USB_GND"] = ("J1.3", "R3.1")
        nets["BOARD_GND"] = ("U1.3",)
        nets["FLOATING_GND"] = ("R3.2",)
    elif fault != "missing":
        nets["BOARD_GND"] = ("U1.3", "R3.2")
    return base.model_copy(
        update={
            "components": components,
            "nets": nets,
            "dnp_components": dnp,
            "component_symbols": symbols,
            "component_pin_numbers": {
                **pins,
                "J1": ("1", "2", "3"),
                "U1": ("1", "2", "3"),
            },
            "pin_functions": {
                **functions,
                "J1.3": "GND",
                "U1.3": "AGND",
            },
            "pin_electrical_types": {
                **electrical_types,
                "J1.1": "passive",
                "J1.2": "passive",
                "J1.3": "passive",
                "U1.1": "input",
                "U1.2": "input",
                "U1.3": "power_in",
            },
        }
    )


def lint_report(
    observed: NetlistContract,
    path_map: UsbDataPathMap | None,
    *,
    override: DesignLintRuleOverride | None = None,
    ignore: DesignLintIgnore | None = None,
):
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-data-path",
        observed=observed,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        "synthetic-usb-data-path",
        coach,
        DesignLintPolicy(
            usb_data_path_map=path_map,
            rules=() if override is None else (override,),
            ignores=() if ignore is None else (ignore,),
        ),
    )
