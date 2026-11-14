"""Validate external-protection coverage against native USB shunt exports."""

from __future__ import annotations

from collections.abc import Mapping

from .ci_hosted_support import HostedLog
from .hwrepo.connector_coverage_models import (
    ConnectorCoverageEntry,
    ConnectorCoverageReport,
    ConnectorMappedPinEvidence,
)
from .hwrepo.contract_coach_models import ContractCoachReport
from .hwrepo.design_lint import evaluate as evaluate_design_lint
from .hwrepo.design_lint_policy_models import DesignLintPolicy
from .hwrepo.design_lint_report_models import DesignLintReport
from .hwrepo.external_protection import evaluate as evaluate_external_protection
from .hwrepo.external_protection_models import (
    ExternalProtectionChannelRequirement,
    ExternalProtectionDeviceRequirement,
    ExternalProtectionInterfaceRequirement,
    ExternalProtectionMap,
)
from .hwrepo.netlist_contract_models import NetlistContract

RULE_IDS = frozenset(
    {
        "protection.channel_capacitance_budget_exceeded",
        "protection.mapped_device_mismatch",
        "protection.unreviewed_interface_pin",
    }
)


def _requirements() -> ExternalProtectionMap:
    return ExternalProtectionMap(
        basis="Synthetic USB connector and protection-array pin map",
        interfaces=(
            ExternalProtectionInterfaceRequirement(
                connector_reference="J1",
                expected_connector_symbol="Connector:USB_A",
                expected_connector_footprint="Synthetic:USB-A",
                connector_pin="J1.1",
                signal_net="USB_DP",
                disposition="required",
                basis="Synthetic reviewed data-pin protection channel",
                channels=(
                    ExternalProtectionChannelRequirement(
                        device_reference="U6",
                        signal_pin="U6.1",
                        reference_pin="U6.2",
                        reference_net="BOARD_GND",
                    ),
                ),
            ),
        ),
        devices=(
            ExternalProtectionDeviceRequirement(
                reference="U6",
                expected_symbol="Synthetic:UsbProtectionArray",
                expected_footprint="Synthetic:DFN-6",
                pin_nets={
                    "U6.1": "USB_DP",
                    "U6.2": "BOARD_GND",
                    "U6.3": "USB_DM",
                    "U6.4": "BOARD_GND",
                    "U6.5": "BOARD_GND",
                },
                unmapped_pin_reasons={"U6.6": "Synthetic package pin is not connected"},
            ),
        ),
    )


def _capacitance_requirements(maximum_signal_capacitance_pf: float) -> ExternalProtectionMap:
    """Add a synthetic authored capacitance rating to the fixture's exact U6 identity."""
    requirements = _requirements()
    interface = requirements.interfaces[0]
    channel = interface.channels[0].model_copy(
        update={
            "maximum_channel_capacitance_pf": 1.2,
            "capacitance_basis": "Synthetic vendor maximum for U6 pin 1",
        }
    )
    reviewed_interface = interface.model_copy(
        update={
            "channels": (channel,),
            "maximum_signal_capacitance_pf": maximum_signal_capacitance_pf,
            "capacitance_limit_basis": "Synthetic interface capacitance budget",
        }
    )
    device = requirements.devices[0].model_copy(update={"expected_value": "UsbProtectionArray"})
    return ExternalProtectionMap(
        basis=requirements.basis,
        interfaces=(reviewed_interface,),
        devices=(device,),
    )


def _connector_coverage() -> ConnectorCoverageReport:
    return ConnectorCoverageReport(
        status="COMPLETE",
        scope="Synthetic USB connector signal-pin review",
        inventory_review_basis="The tooling-owned fixture maps its USB data contacts",
        entries=(
            ConnectorCoverageEntry(
                reference="J1",
                status="COVERED",
                interface_id="usb-port-1",
                basis="Synthetic connector pin map",
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


def _report(
    case: str,
    observed: NetlistContract,
    netlist_sha256: str,
    *,
    requirements: ExternalProtectionMap | None,
) -> tuple[DesignLintReport, str]:
    project_id = f"synthetic-usb-external-protection-{case}"
    coverage = evaluate_external_protection(
        requirements,
        observed,
        _connector_coverage(),
        netlist_sha256,
    )
    coach = ContractCoachReport(
        status="READY_FOR_REVIEW",
        project_id=project_id,
        observed=observed,
        netlist_sha256=netlist_sha256,
    )
    return (
        evaluate_design_lint(
            project_id,
            coach,
            DesignLintPolicy(),
            external_protection_coverage=coverage,
        ),
        coverage.status,
    )


def validate_usb_external_protection_fixture_reports(
    observations: Mapping[tuple[str, str], NetlistContract],
    netlist_hashes: Mapping[tuple[str, str], str],
    source_hashes: Mapping[str, str],
    *,
    project: str,
    kicad_version: str,
    image: str,
    log: HostedLog,
) -> None:
    """Check the native control, wrong-return fault, and missing-map prompt."""
    control_key = ("protection-shunt-common-reference", "first")
    fault_key = ("protection-shunt-pin-fault", "first")
    for case, key in (
        ("protection-shunt-common-reference", control_key),
        ("protection-shunt-pin-fault", fault_key),
    ):
        if key not in observations or key not in netlist_hashes:
            raise ValueError(f"Native external-protection fixture omitted {case}")
        if case not in source_hashes:
            raise ValueError(f"Native external-protection fixture omitted source hash for {case}")

    requirement = _requirements()
    control, control_coverage = _report(
        "control",
        observations[control_key],
        netlist_hashes[control_key],
        requirements=requirement,
    )
    fault, fault_coverage = _report(
        "return-fault",
        observations[fault_key],
        netlist_hashes[fault_key],
        requirements=requirement,
    )
    unreviewed, unreviewed_coverage = _report(
        "unmapped",
        observations[control_key],
        netlist_hashes[control_key],
        requirements=None,
    )
    capacitance_fault, capacitance_fault_coverage = _report(
        "capacitance-fault",
        observations[control_key],
        netlist_hashes[control_key],
        requirements=_capacitance_requirements(1.0),
    )
    capacitance_control, capacitance_control_coverage = _report(
        "capacitance-control",
        observations[control_key],
        netlist_hashes[control_key],
        requirements=_capacitance_requirements(1.2),
    )
    control_findings = tuple(item for item in control.findings if item.rule_id in RULE_IDS)
    fault_findings = tuple(item for item in fault.findings if item.rule_id in RULE_IDS)
    unreviewed_findings = tuple(item for item in unreviewed.findings if item.rule_id in RULE_IDS)
    cap_fault_findings = tuple(
        item for item in capacitance_fault.findings if item.rule_id in RULE_IDS
    )
    cap_control_findings = tuple(
        item for item in capacitance_control.findings if item.rule_id in RULE_IDS
    )
    if control_coverage != "COMPLETE" or control_findings:
        raise ValueError("Native mapped protection control did not remain covered and clear")
    if fault_coverage != "INCOMPLETE" or len(fault_findings) != 1:
        raise ValueError("Native protection-return fault did not produce one mapped mismatch")
    mismatch = fault_findings[0]
    if mismatch.rule_id != "protection.mapped_device_mismatch" or not any(
        issue.startswith("U6.2 is on USB_DP; expected BOARD_GND")
        for issue in mismatch.evidence.get("issues", ())
    ):
        raise ValueError("Native protection mismatch omitted the exact U6.2 return-net fault")
    if unreviewed_coverage != "UNDECLARED" or tuple(
        item.rule_id for item in unreviewed_findings
    ) != ("protection.unreviewed_interface_pin",):
        raise ValueError("Native unmapped connector control omitted its applicability prompt")
    if capacitance_fault_coverage != "COMPLETE" or tuple(
        item.rule_id for item in cap_fault_findings
    ) != ("protection.channel_capacitance_budget_exceeded",):
        raise ValueError("Native over-budget protection capacitance did not prompt for review")
    if capacitance_control_coverage != "COMPLETE" or cap_control_findings:
        raise ValueError("Native within-budget protection capacitance control did not remain clear")
    cap_fault = cap_fault_findings[0]
    if cap_fault.evidence.get("channel_maxima") != ("U6.1: 1.2 pF max (UsbProtectionArray)",):
        raise ValueError("Native capacitance finding omitted its exact protector identity evidence")

    log.event(
        "usb-data-path-fixture/external-protection-contract",
        "PASS",
        project=project,
        kicad_version=kicad_version,
        image=image,
        control_source_sha256=source_hashes[control_key[0]],
        control_netlist_sha256=netlist_hashes[control_key],
        control_coverage_status=control_coverage,
        control_findings="none",
        return_fault_source_sha256=source_hashes[fault_key[0]],
        return_fault_netlist_sha256=netlist_hashes[fault_key],
        return_fault_rule=mismatch.rule_id,
        return_fault_subject=mismatch.subject,
        return_fault_issues=";".join(mismatch.evidence.get("issues", ())),
        unmapped_coverage_status=unreviewed_coverage,
        unmapped_rule=unreviewed_findings[0].rule_id,
        unmapped_subject=unreviewed_findings[0].subject,
        capacitance_fault_rule=cap_fault.rule_id,
        capacitance_fault_subject=cap_fault.subject,
        capacitance_fault_netlist_sha256=netlist_hashes[control_key],
        capacitance_control_findings="none",
    )
