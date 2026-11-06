"""Minimal synthetic netlists shared by USB-C VBUS heuristic regressions."""

from __future__ import annotations

from kicad_tooling.hwrepo.analysis_state_models import AnalysisNotApplicable, AnalysisPending
from kicad_tooling.hwrepo.design_lint import evaluate
from kicad_tooling.hwrepo.models import (
    ComponentContract,
    ContractCoachReport,
    DesignLintPolicy,
    NetlistContract,
)
from kicad_tooling.hwrepo.usb_c_models import (
    UsbCAnalysis,
    UsbCcLineRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCVbusCapacitanceRequirement,
    UsbCVbusCapacitorRequirement,
)
from kicad_tooling.hwrepo.usb_c_ports import UsbCPortRosterContext


def usb_c_vbus_netlist(
    *,
    connector: str = "J1",
    capacitor: bool = False,
    dnp_capacitor: bool = False,
    capacitor_return_net: str = "GND",
    ambiguous_capacitor_pin: bool = False,
) -> NetlistContract:
    """Return a four-pin synthetic USB-C connector with an optional VBUS cap."""
    components = {connector: ComponentContract(value="Synthetic USB-C", footprint="Synthetic:UsbC")}
    symbols = {connector: "Synthetic:UsbCPort"}
    pin_numbers = {connector: ("1", "2", "3", "4")}
    functions = {
        f"{connector}.1": "CC1",
        f"{connector}.2": "CC2",
        f"{connector}.3": "VBUS",
        f"{connector}.4": "GND",
    }
    nets: dict[str, tuple[str, ...]] = {
        "CC1": (f"{connector}.1",),
        "CC2": (f"{connector}.2",),
        "VBUS_PORT": (f"{connector}.3",),
        "GND": (f"{connector}.4",),
    }
    if capacitor or dnp_capacitor or ambiguous_capacitor_pin:
        components["C1"] = ComponentContract(value="4.7uF", footprint="Synthetic:C_0603")
        symbols["C1"] = "Device:C"
        pin_numbers["C1"] = ("1", "2")
        functions.update({"C1.1": "~", "C1.2": "~"})
        nets["VBUS_PORT"] = (*nets["VBUS_PORT"], "C1.1")
        nets.setdefault(capacitor_return_net, ())
        nets[capacitor_return_net] = (*nets[capacitor_return_net], "C1.2")
    if ambiguous_capacitor_pin:
        nets["OTHER_RAIL"] = ("C1.1",)
    dnp = ("C1",) if dnp_capacitor else ()
    return NetlistContract(
        components=components,
        nets=nets,
        dnp_components=dnp,
        component_symbols=symbols,
        pin_functions=functions,
        component_pin_numbers=pin_numbers,
    )


def usb_c_capacitance_roster(mode: str) -> UsbCPortRosterContext:
    """Build a mapped J1 port with one requested capacitance disposition."""
    if mode == "required":
        capacitance: UsbCVbusCapacitanceRequirement | AnalysisPending | AnalysisNotApplicable = (
            UsbCVbusCapacitanceRequirement(
                basis="Synthetic required capacitance source",
                minimum_nf=1,
                maximum_nf=10_000,
                capacitors=(
                    UsbCVbusCapacitorRequirement(
                        reference="C1",
                        symbol="Device:C",
                        footprint="Synthetic:C_0603",
                        pins=(
                            UsbCNetPinAssignment(pin="C1.1", net="VBUS_PORT"),
                            UsbCNetPinAssignment(pin="C1.2", net="GND"),
                        ),
                    ),
                ),
            )
        )
    elif mode == "not_applicable":
        capacitance = AnalysisNotApplicable(
            mode="not_applicable", reason="Synthetic source does not require port capacitance."
        )
    else:
        capacitance = AnalysisPending(reason="Synthetic capacitance scope needs review.")
    port = UsbCPortRequirement(
        id="J1-port",
        basis="Synthetic USB-C pinout",
        connector="J1",
        role="sink",
        cc1=UsbCcLineRequirement(
            connector_pin="J1.1",
            net="CC1",
            attachment=UsbCcResistorAttachment(
                kind="resistor",
                behavior="rd",
                reference="R1",
                rail_net="GND",
                minimum_ohms=4_500,
                maximum_ohms=6_000,
            ),
        ),
        cc2=UsbCcLineRequirement(
            connector_pin="J1.2",
            net="CC2",
            attachment=UsbCcResistorAttachment(
                kind="resistor",
                behavior="rd",
                reference="R2",
                rail_net="GND",
                minimum_ohms=4_500,
                maximum_ohms=6_000,
            ),
        ),
        vbus_net="VBUS_PORT",
        vbus_pins=(
            UsbCNetPinAssignment(pin="J1.3", net="VBUS_PORT"),
            UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
        ),
        ground_net="GND",
        ground_pins=("J1.4", "U1.2"),
        vbus_capacitance=capacitance,
        protection=AnalysisPending(reason="Synthetic protection scope is outside this fixture."),
    )
    analysis = UsbCAnalysis(basis="Synthetic USB-C role map", ports=(port,))
    return UsbCPortRosterContext(
        state="required",
        analysis=analysis,
        source_path="tests/fixtures/synthetic-usb-c/electrical.json",
        source_sha256="c" * 64,
    )


def usb_c_vbus_report(
    netlist: NetlistContract,
    *,
    policy: DesignLintPolicy | None = None,
    roster: UsbCPortRosterContext | None = None,
):
    """Evaluate a fixture netlist through the shared design-lint service."""
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-usb-c-vbus",
        observed=netlist,
        netlist_sha256="a" * 64,
    )
    return evaluate(
        coach.project_id,
        coach,
        policy or DesignLintPolicy(),
        usb_c_port_roster=roster or UsbCPortRosterContext(state="not_configured"),
    )
