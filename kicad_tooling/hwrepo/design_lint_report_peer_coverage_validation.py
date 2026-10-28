from __future__ import annotations

from .can_peer_reference_models import CanPeerReferenceCoverageReport
from .component_peer_pin_models import ComponentPeerPinRuleCoverage
from .design_lint_finding_models import DesignLintFinding
from .digital_peer_voltage_models import DigitalPeerVoltageRuleCoverage
from .i2c_peer_reference_models import I2cPeerReferenceCoverageReport
from .model_primitives import Digest
from .rs485_peer_reference_models import Rs485PeerReferenceCoverageReport
from .serial_peer_reference_models import SerialPeerReferenceCoverageReport
from .spi_peer_reference_models import SpiPeerReferenceCoverageReport
from .usb_peer_reference_models import UsbPeerReferenceCoverageReport


def validate_peer_coverage(
    *,
    netlist_sha256: Digest | None,
    findings: tuple[DesignLintFinding, ...],
    digital_peer_voltage_coverage: tuple[DigitalPeerVoltageRuleCoverage, ...],
    component_peer_pin_coverage: tuple[ComponentPeerPinRuleCoverage, ...],
    usb_peer_reference_coverage: UsbPeerReferenceCoverageReport | None,
    serial_peer_reference_coverage: SerialPeerReferenceCoverageReport | None,
    i2c_peer_reference_coverage: I2cPeerReferenceCoverageReport | None,
    spi_peer_reference_coverage: SpiPeerReferenceCoverageReport | None,
    can_peer_reference_coverage: CanPeerReferenceCoverageReport | None,
    rs485_peer_reference_coverage: Rs485PeerReferenceCoverageReport | None,
) -> None:
    voltage_coverage_ids = [item.rule_id for item in digital_peer_voltage_coverage]
    if len(voltage_coverage_ids) != len(set(voltage_coverage_ids)):
        raise ValueError("Digital-peer voltage coverage entries must use unique rule IDs")
    for item in digital_peer_voltage_coverage:
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("Digital-peer voltage coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("Digital-peer voltage candidate counts must match report findings")
    component_peer_pin_rule_ids = [item.rule_id for item in component_peer_pin_coverage]
    if len(component_peer_pin_rule_ids) != len(set(component_peer_pin_rule_ids)):
        raise ValueError("Component peer-pin coverage entries must use unique rule IDs")
    expected_component_peer_pin_rule_ids = {
        "component.peer_power_output_unconnected",
        "component.peer_signal_output_unconnected",
        "component.peer_signal_input_unconnected",
        "component.peer_bidirectional_pin_unconnected",
        "component.peer_power_input_assignment_divergence",
        "component.peer_power_input_named_assignment_divergence",
        "component.peer_power_input_named_all_open",
        "component.peer_power_input_open_assignment",
        "component.generic_peer_pin_assignment_outlier",
        "component.generic_peer_pin_mixed_open",
        "component.generic_peer_pin_all_open",
    }
    if component_peer_pin_rule_ids and set(component_peer_pin_rule_ids) != (
        expected_component_peer_pin_rule_ids
    ):
        raise ValueError("Component peer-pin coverage must include every supported rule")
    for item in component_peer_pin_coverage:
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("Component peer-pin coverage must use this report's netlist")
        expected_findings = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.finding_count != expected_findings:
            raise ValueError("Component peer-pin findings must match report findings")
    if usb_peer_reference_coverage is not None:
        item = usb_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("USB peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("USB peer-reference candidate counts must match report findings")
    if serial_peer_reference_coverage is not None:
        item = serial_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("Serial peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("Serial peer-reference candidate counts must match report findings")
    if i2c_peer_reference_coverage is not None:
        item = i2c_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("I2C peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("I2C peer-reference candidate counts must match report findings")
    if spi_peer_reference_coverage is not None:
        item = spi_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("SPI peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("SPI peer-reference candidate counts must match report findings")
    if can_peer_reference_coverage is not None:
        item = can_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("CAN peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("CAN peer-reference candidate counts must match report findings")
    if rs485_peer_reference_coverage is not None:
        item = rs485_peer_reference_coverage
        if netlist_sha256 is not None and item.netlist_sha256 != netlist_sha256:
            raise ValueError("RS-485 peer-reference coverage must use this report's netlist")
        expected_groups = sum(finding.rule_id == item.rule_id for finding in findings)
        if item.candidate_group_count != expected_groups:
            raise ValueError("RS-485 peer-reference candidate counts must match report findings")
