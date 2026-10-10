"""Synthetic external-protection maps, netlists, and lint report builders."""

from __future__ import annotations

import hashlib
from typing import Literal

from kicad_tooling.hwrepo.design_lint import evaluate as evaluate_design_lint
from kicad_tooling.hwrepo.external_protection import evaluate
from kicad_tooling.hwrepo.models import (
    AnalysisNotApplicable,
    ComponentContract,
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
    ContractCoachReport,
    DesignLintPolicy,
    DesignLintReport,
    ExternalProtectionChannelRequirement,
    ExternalProtectionDeviceRequirement,
    ExternalProtectionInterfaceRequirement,
    ExternalProtectionMap,
    NetlistContract,
    UsbCAnalysis,
    UsbCcLineRequirement,
    UsbCcResistorAttachment,
    UsbCNetPinAssignment,
    UsbCPortRequirement,
    UsbCProtectionAnalysis,
    UsbCProtectionComponentRequirement,
)


def usb_c_protection_requirement() -> UsbCAnalysis:
    """Build the minimal typed USB-C map needed by protection-coverage tests."""
    protection = UsbCProtectionAnalysis(
        basis="Synthetic reviewed CC protector pin map",
        components=(
            UsbCProtectionComponentRequirement(
                reference="D1",
                symbol="Synthetic:UsbProtection",
                footprint="Package_DFN:DFN-6",
                pins=(
                    UsbCNetPinAssignment(pin="D1.1", net="CC1"),
                    UsbCNetPinAssignment(pin="D1.2", net="GND"),
                ),
            ),
        ),
    )
    return UsbCAnalysis(
        basis="Synthetic USB-C source port for protection-coverage test",
        ports=(
            UsbCPortRequirement(
                id="host-port",
                basis="Reviewed synthetic USB-C receptacle pinout",
                connector="J1",
                role="source",
                cc1=UsbCcLineRequirement(
                    connector_pin="J1.4",
                    net="CC1",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R1",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                cc2=UsbCcLineRequirement(
                    connector_pin="J1.5",
                    net="CC2",
                    attachment=UsbCcResistorAttachment(
                        kind="resistor",
                        behavior="rp",
                        reference="R2",
                        rail_net="+5V",
                        minimum_ohms=50_000,
                        maximum_ohms=60_000,
                    ),
                ),
                vbus_net="VBUS_PORT",
                vbus_pins=(
                    UsbCNetPinAssignment(pin="J1.1", net="VBUS_PORT"),
                    UsbCNetPinAssignment(pin="U1.1", net="VBUS_SYSTEM"),
                ),
                ground_net="GND",
                ground_pins=("J1.2", "U1.5"),
                vbus_capacitance=AnalysisNotApplicable(
                    mode="not_applicable",
                    reason="Synthetic protection test does not assess port-side capacitance.",
                ),
                source_rail="+5V",
                protection=protection,
            ),
        ),
    )


def protection_map(
    *,
    disposition: Literal["required", "not_required"] = "required",
    unmapped_pin_reasons: dict[str, str] | None = None,
) -> ExternalProtectionMap:
    channels = (
        (
            ExternalProtectionChannelRequirement(
                device_reference="D1",
                signal_pin="D1.1",
                reference_pin="D1.2",
                reference_net="GND",
            ),
        )
        if disposition == "required"
        else ()
    )
    devices = (
        (
            ExternalProtectionDeviceRequirement(
                reference="D1",
                expected_symbol="Synthetic:TVS",
                expected_footprint="Synthetic:SOD323",
                pin_nets={"D1.1": "USB_DP", "D1.2": "GND"},
                unmapped_pin_reasons=unmapped_pin_reasons or {},
            ),
        )
        if disposition == "required"
        else ()
    )
    return ExternalProtectionMap(
        basis="Synthetic reviewed USB interface and protector pinout",
        interfaces=(
            ExternalProtectionInterfaceRequirement(
                connector_reference="J1",
                expected_connector_symbol="Synthetic:UsbPort",
                expected_connector_footprint="Synthetic:USB-C",
                connector_pin="J1.1",
                signal_net="USB_DP",
                disposition=disposition,
                basis=(
                    "Synthetic datasheet-mapped TVS channel"
                    if disposition == "required"
                    else "Synthetic reviewed interface has integrated protection"
                ),
                channels=channels,
            ),
        ),
        devices=devices,
    )


def observed_netlist(
    *,
    fault: str | None = None,
    extra_device_pin: bool = False,
    dnp: tuple[str, ...] = (),
) -> NetlistContract:
    connector_nets = {"USB_DP": ("J1.1", "D1.1"), "USB_DM": ("J1.2",), "GND": ("D1.2",)}
    if fault == "protector-wrong-net":
        connector_nets = {"USB_DP": ("J1.1",), "USB_DM": ("J1.2", "D1.1"), "GND": ("D1.2",)}
    elif fault == "connector-wrong-net":
        connector_nets = {"USB_DP": ("D1.1",), "USB_DM": ("J1.1", "J1.2"), "GND": ("D1.2",)}
    component_pin_numbers = {
        "J1": ("1", "2"),
        "D1": ("1", "2", *(("3",) if extra_device_pin else ())),
    }
    return NetlistContract(
        components={
            "J1": ComponentContract(value="Synthetic USB connector", footprint="Synthetic:USB-C"),
            "D1": ComponentContract(value="Synthetic TVS", footprint="Synthetic:SOD323"),
        },
        nets=connector_nets,
        dnp_components=dnp,
        component_symbols={"J1": "Synthetic:UsbPort", "D1": "Synthetic:TVS"},
        pin_functions={"J1.1": "D+", "J1.2": "D-", "D1.1": "IO", "D1.2": "GND"},
        component_pin_numbers=component_pin_numbers,
    )


def connector_coverage() -> ConnectorCoverageReport:
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic reviewed interface pin map",
        inventory_review_basis="Synthetic review covered the complete connector inventory",
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="usb-data",
                basis="Synthetic connector datasheet pinout",
                mapped_pins=(
                    ConnectorMappedPinEvidence(
                        interface_pin_number="1",
                        interface_signal="USB_D+",
                        component_pin="J1.1",
                        symbol_function="D+",
                        nets=("USB_DP",),
                    ),
                ),
            ),
        ),
    )


def protection_lint_report(
    requirements: ExternalProtectionMap | None,
    observed: NetlistContract,
) -> tuple[str, DesignLintReport]:
    """Bind the synthetic native-netlist model and project protection map to lint evidence."""
    netlist_sha256 = hashlib.sha256(observed.model_dump_json().encode("utf-8")).hexdigest()
    coverage = evaluate(requirements, observed, connector_coverage(), netlist_sha256)
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id="synthetic-external-protection",
        netlist_sha256=netlist_sha256,
        observed=observed,
    )
    report = evaluate_design_lint(
        coach.project_id,
        coach,
        DesignLintPolicy(),
        external_protection_coverage=coverage,
    )
    return netlist_sha256, report
