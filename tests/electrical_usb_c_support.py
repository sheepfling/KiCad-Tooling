"""Synthetic USB-C electrical contract and netlist fixtures."""

from __future__ import annotations

from typing import Literal

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    NetlistContract,
)
from kicad_tooling.hwrepo.usb_c_models import (
    UsbCAnalysis,
    UsbCcControllerAttachment,
    UsbCcLineRequirement,
    UsbCControllerRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCProtectionAnalysis,
    UsbCProtectionComponentRequirement,
    UsbCVbusCapacitanceRequirement,
    UsbCVbusCapacitorRequirement,
    UsbCVbusPathElement,
    UsbCVbusPathRequirement,
)


def usb_c_requirement(
    *,
    role: Literal["source", "sink", "dual_role", "debug_accessory"] = "source",
    controller: bool = False,
    connector: str = "J1",
    board_component: str = "U1",
    controller_reference: str = "U2",
    protection_reference: str = "D1",
    resistor_references: tuple[str, str] = ("R1", "R2"),
    vbus_path: bool = False,
    vbus_capacitance: bool = False,
    vbus_capacitor_reference: str = "C1",
    vbus_capacitor_footprint: str = "Synthetic:C_0603",
) -> UsbCAnalysis:
    cc1_attachment = (
        UsbCcControllerAttachment(kind="controller", controller_pin=f"{controller_reference}.5")
        if controller
        else UsbCcResistorAttachment(
            kind="resistor",
            behavior="rd" if role == "sink" else "rp",
            reference=resistor_references[0],
            rail_net="GND" if role == "sink" else "+5V",
            minimum_ohms=5_000 if role == "sink" else 50_000,
            maximum_ohms=5_200 if role == "sink" else 60_000,
        )
    )
    cc2_attachment = (
        UsbCcControllerAttachment(kind="controller", controller_pin=f"{controller_reference}.6")
        if controller
        else UsbCcResistorAttachment(
            kind="resistor",
            behavior="rd" if role == "sink" else "rp",
            reference=resistor_references[1],
            rail_net="GND" if role == "sink" else "+5V",
            minimum_ohms=5_000 if role == "sink" else 50_000,
            maximum_ohms=5_200 if role == "sink" else 60_000,
        )
    )
    return UsbCAnalysis(
        basis="Synthetic USB-C port role and pinout requirements",
        ports=(
            UsbCPortRequirement(
                id="host-port",
                basis="Reviewed synthetic receptacle role and pinout",
                connector=connector,
                role=role,
                cc1=UsbCcLineRequirement(
                    connector_pin=f"{connector}.4", net="CC1", attachment=cc1_attachment
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin=f"{connector}.5", net="CC2", attachment=cc2_attachment
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin=f"{connector}.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin=f"{board_component}.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=(
                    f"{connector}.2",
                    f"{connector}.3",
                    f"{board_component}.5",
                ),
                vbus_capacitance=(
                    UsbCVbusCapacitanceRequirement(
                        basis="Synthetic port-side capacitance range",
                        minimum_nf=4_500,
                        maximum_nf=5_000,
                        capacitors=(
                            UsbCVbusCapacitorRequirement(
                                reference=vbus_capacitor_reference,
                                symbol="Device:C",
                                footprint=vbus_capacitor_footprint,
                                pins=(
                                    UsbCNetPinAssignment(
                                        pin=f"{vbus_capacitor_reference}.1", net="VBUS_PORT"
                                    ),
                                    UsbCNetPinAssignment(
                                        pin=f"{vbus_capacitor_reference}.2", net="GND"
                                    ),
                                ),
                            ),
                        ),
                    )
                    if vbus_capacitance
                    else AnalysisNotApplicable(
                        mode="not_applicable",
                        reason="This synthetic USB-C case does not assess port-side capacitance.",
                    )
                ),
                source_rail="+5V" if role == "source" and not controller else None,
                controller=(
                    UsbCControllerRequirement(
                        reference=controller_reference,
                        symbol="Synthetic:TypeCController",
                        footprint="Package_QFN:QFN-16",
                    )
                    if controller
                    else None
                ),
                vbus_path=(
                    UsbCVbusPathRequirement(
                        id="input-path",
                        basis="Synthetic reviewed connector-to-system VBUS path",
                        connector_pin=f"{connector}.1",
                        connector_net="VBUS_PORT",
                        board_pin=f"{board_component}.1",
                        board_net="VBUS_SYSTEM",
                        elements=(
                            UsbCVbusPathElement(
                                reference="F1",
                                symbol="Device:Fuse",
                                footprint="Fuse:Fuse_1206_3216Metric",
                                port_side_net="VBUS_PORT",
                                system_side_net="VBUS_FUSED",
                                port_side_pins=("F1.1",),
                                system_side_pins=("F1.2",),
                                pin_assignments=(
                                    UsbCNetPinAssignment(pin="F1.1", net="VBUS_PORT"),
                                    UsbCNetPinAssignment(pin="F1.2", net="VBUS_FUSED"),
                                ),
                            ),
                            UsbCVbusPathElement(
                                reference="U3",
                                symbol="Synthetic:LoadSwitch",
                                footprint="Package_DFN:DFN-6",
                                port_side_net="VBUS_FUSED",
                                system_side_net="VBUS_SYSTEM",
                                port_side_pins=("U3.1", "U3.2"),
                                system_side_pins=("U3.3",),
                                pin_assignments=(
                                    UsbCNetPinAssignment(pin="U3.1", net="VBUS_FUSED"),
                                    UsbCNetPinAssignment(pin="U3.2", net="VBUS_FUSED"),
                                    UsbCNetPinAssignment(pin="U3.3", net="VBUS_SYSTEM"),
                                    UsbCNetPinAssignment(pin="U3.4", net="SWITCH_ENABLE"),
                                ),
                            ),
                        ),
                    )
                    if vbus_path
                    else None
                ),
                protection=UsbCProtectionAnalysis(
                    basis="Synthetic reviewed CC ESD part and pin assignments",
                    components=(
                        UsbCProtectionComponentRequirement(
                            reference=protection_reference,
                            symbol="Synthetic:UsbProtection",
                            footprint="Package_DFN:DFN-6",
                            pins=(
                                UsbCNetPinAssignment(pin=f"{protection_reference}.1", net="CC1"),
                                UsbCNetPinAssignment(pin=f"{protection_reference}.2", net="GND"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def usb_c_netlist(
    *,
    role: Literal["source", "sink", "dual_role", "debug_accessory"] = "source",
    controller: bool = False,
    dnp: tuple[str, ...] = (),
    footprint: str = "Package_DFN:DFN-6",
    connector: str = "J1",
    board_component: str = "U1",
    controller_reference: str = "U2",
    protection_reference: str = "D1",
    resistor_references: tuple[str, str] = ("R1", "R2"),
    vbus_path: bool = False,
) -> NetlistContract:
    components = {
        connector: ComponentContract(value="Synthetic USB-C receptacle", footprint=""),
        board_component: ComponentContract(value="Synthetic system connector", footprint=""),
        protection_reference: ComponentContract(value="Synthetic protection", footprint=footprint),
        "C1": ComponentContract(value="4.7uF", footprint="Synthetic:C_0603"),
    }
    symbols = {
        connector: "Synthetic:UsbCReceptacle",
        board_component: "Synthetic:SystemConnector",
        protection_reference: "Synthetic:UsbProtection",
        "C1": "Device:C",
    }
    nets: dict[str, tuple[str, ...]] = {
        "CC1": (f"{connector}.4", f"{protection_reference}.1"),
        "CC2": (f"{connector}.5",),
        "VBUS_PORT": (f"{connector}.1",),
        "VBUS_SYSTEM": (f"{board_component}.1",),
        "GND": (
            f"{connector}.2",
            f"{connector}.3",
            f"{board_component}.5",
            f"{protection_reference}.2",
            "C1.2",
        ),
    }
    nets["VBUS_PORT"] = (*nets["VBUS_PORT"], "C1.1")
    pin_functions = {
        f"{connector}.1": "VBUS",
        f"{connector}.2": "GND",
        f"{connector}.3": "GND",
        f"{connector}.4": "CC1",
        f"{connector}.5": "CC2",
        f"{board_component}.1": "VBUS",
        f"{board_component}.5": "GND",
        f"{protection_reference}.1": "CC1",
        f"{protection_reference}.2": "GND",
        "C1.1": "1",
        "C1.2": "2",
    }
    pin_numbers = {
        connector: ("1", "2", "3", "4", "5"),
        board_component: ("1", "5"),
        protection_reference: ("1", "2"),
        "C1": ("1", "2"),
    }
    if vbus_path:
        components.update(
            {
                "F1": ComponentContract(value="PTC fuse", footprint="Fuse:Fuse_1206_3216Metric"),
                "U3": ComponentContract(
                    value="Synthetic load switch", footprint="Package_DFN:DFN-6"
                ),
            }
        )
        symbols.update({"F1": "Device:Fuse", "U3": "Synthetic:LoadSwitch"})
        nets["VBUS_PORT"] = (*nets["VBUS_PORT"], "F1.1")
        nets["VBUS_FUSED"] = ("F1.2", "U3.1", "U3.2")
        nets["VBUS_SYSTEM"] = (*nets["VBUS_SYSTEM"], "U3.3")
        nets["SWITCH_ENABLE"] = ("U3.4",)
        pin_functions.update(
            {
                "F1.1": "1",
                "F1.2": "2",
                "U3.1": "VIN",
                "U3.2": "VIN_ALT",
                "U3.3": "VOUT",
                "U3.4": "EN",
            }
        )
        pin_numbers.update({"F1": ("1", "2"), "U3": ("1", "2", "3", "4", "5", "6")})
    if controller:
        components[controller_reference] = ComponentContract(
            value="Synthetic USB-C controller", footprint="Package_QFN:QFN-16"
        )
        symbols[controller_reference] = "Synthetic:TypeCController"
        nets["CC1"] = (*nets["CC1"], f"{controller_reference}.5")
        nets["CC2"] = (*nets["CC2"], f"{controller_reference}.6")
        pin_functions.update(
            {f"{controller_reference}.5": "CC1", f"{controller_reference}.6": "CC2"}
        )
        pin_numbers[controller_reference] = tuple(str(index) for index in range(1, 17))
    else:
        first_resistor, second_resistor = resistor_references
        resistor_value = "5.1k" if role == "sink" else "56k"
        components.update(
            {
                first_resistor: ComponentContract(
                    value=resistor_value, footprint="Synthetic:R_0603"
                ),
                second_resistor: ComponentContract(
                    value=resistor_value, footprint="Synthetic:R_0603"
                ),
            }
        )
        symbols.update({first_resistor: "Device:R", second_resistor: "Device:R"})
        nets["CC1"] = (*nets["CC1"], f"{first_resistor}.1")
        nets["CC2"] = (*nets["CC2"], f"{second_resistor}.1")
        resistor_rail = "GND" if role == "sink" else "+5V"
        nets[resistor_rail] = (
            *nets.get(resistor_rail, ()),
            f"{first_resistor}.2",
            f"{second_resistor}.2",
        )
        pin_functions.update(
            {
                f"{first_resistor}.1": "1",
                f"{first_resistor}.2": "2",
                f"{second_resistor}.1": "1",
                f"{second_resistor}.2": "2",
            }
        )
        pin_numbers.update({first_resistor: ("1", "2"), second_resistor: ("1", "2")})
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=pin_functions,
        component_pin_numbers=pin_numbers,
    )
