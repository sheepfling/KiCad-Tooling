"""Interfaces hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.interface_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]


def test_interface_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("interfaces",))
    i2c_fault = reports["i2c_array_fault"]
    i2c_control = reports["i2c_array_control"]
    i2c_coverage_fault = i2c_fault["i2c_pullup_heuristic_coverage"]
    i2c_coverage_control = i2c_control["i2c_pullup_heuristic_coverage"]
    assert i2c_fault["status"] == "REVIEW"
    assert i2c_coverage_fault["status"] == "OPEN"
    assert i2c_coverage_fault["entries"][0]["status"] == "OPEN"
    assert i2c_coverage_fault["netlist_sha256"] == i2c_fault["netlist_sha256"]
    assert i2c_coverage_fault["source_path"] == (
        "projects/synthetic-i2c-array/tests/electrical.json"
    )
    assert i2c_coverage_fault["source_sha256"] == i2c_coverage_control["source_sha256"]
    assert i2c_control["status"] == "REVIEW"
    assert i2c_coverage_control["status"] == "COMPLETE"
    assert i2c_coverage_control["entries"][0]["status"] == "COVERED"
    assert i2c_coverage_control["netlist_sha256"] == i2c_control["netlist_sha256"]
    assert i2c_fault["netlist_sha256"] != i2c_control["netlist_sha256"]
    assert {item["rule_id"] for item in i2c_fault["findings"]} == {
        "bus.i2c_missing_pullup",
        "bus.i2c_unmapped_responder",
    }
    assert [item["rule_id"] for item in i2c_control["findings"]] == [
        "bus.i2c_unmapped_responder"
    ], "the array requirement clears only its I2C pull-up hint"

    i2c_contract_fault = reports["i2c_array_contract_fault"]
    i2c_contract_control = reports["i2c_array_contract_control"]
    assert i2c_contract_fault["requirement_sha256"] == i2c_contract_control["requirement_sha256"]
    assert i2c_contract_fault["netlist_sha256"] != i2c_contract_control["netlist_sha256"]
    fault_checks = {item["id"]: item for item in i2c_contract_fault["checks"]}
    control_checks = {item["id"]: item for item in i2c_contract_control["checks"]}
    assert fault_checks["i2c-pullup/main/sda"]["status"] == "FAIL"
    assert fault_checks["i2c-pullup/main/sda"]["observed"] is None
    assert fault_checks["i2c-pullup/main/scl"]["status"] == "PASS"
    assert control_checks["i2c-pullup/main/sda"]["status"] == "PASS"
    assert control_checks["i2c-pullup/main/sda"]["observed"] == 4_700
    assert control_checks["i2c-pullup/main/scl"]["status"] == "PASS"
    assert control_checks["i2c-pullup/main/scl"]["observed"] == 4_700

    i2c_address_fault_case = reports["i2c_address_map_fault"]
    i2c_address_control_case = reports["i2c_address_map_control"]
    assert (
        i2c_address_fault_case["requirement_sha256"]
        == i2c_address_control_case["requirement_sha256"]
    )
    i2c_address_fault = i2c_address_fault_case["report"]
    i2c_address_control = i2c_address_control_case["report"]
    assert i2c_address_fault["status"] == "REVIEW"
    assert i2c_address_fault["i2c_address_coverage"]["status"] == "COMPLETE"
    assert (
        i2c_address_fault["i2c_address_coverage"]["netlist_sha256"]
        == (i2c_address_fault["netlist_sha256"])
    )
    assert i2c_address_fault["netlist_sha256"] != i2c_address_control["netlist_sha256"]
    address_fault_findings = {
        finding["rule_id"]: finding for finding in i2c_address_fault["findings"]
    }
    assert set(address_fault_findings) == {
        "bus.i2c_address_mismatch",
        "bus.i2c_address_collision",
    }
    assert address_fault_findings["bus.i2c_address_mismatch"]["subject"] == "U1 on MAIN: 0x51"
    assert address_fault_findings["bus.i2c_address_collision"]["subject"] == (
        "MAIN: U1, U2 at 0x51"
    )
    assert i2c_address_control["status"] == "PASS"
    assert i2c_address_control["findings"] == []
    assert i2c_address_control["i2c_address_coverage"]["status"] == "COMPLETE"

    protection_fault_case = reports["external_protection_fault"]
    protection_control_case = reports["external_protection_control"]
    assert (
        protection_fault_case["requirement_sha256"] == protection_control_case["requirement_sha256"]
    )
    assert protection_fault_case["netlist_sha256"] != protection_control_case["netlist_sha256"]
    protection_fault = protection_fault_case["report"]
    protection_control = protection_control_case["report"]
    assert protection_fault["status"] == "REVIEW"
    protection_coverage = protection_fault["external_protection_coverage"]
    assert protection_coverage["status"] == "INCOMPLETE"
    assert protection_coverage["netlist_sha256"] == protection_fault_case["netlist_sha256"]
    protection_fault_rule_ids = {finding["rule_id"] for finding in protection_fault["findings"]}
    assert protection_fault_rule_ids == {
        "protection.mapped_device_mismatch",
        "signal.named_pair_without_reviewed_requirement",
    }
    protection_control_rule_ids = {finding["rule_id"] for finding in protection_control["findings"]}
    assert protection_control["status"] == "REVIEW"
    assert protection_control_rule_ids == {"signal.named_pair_without_reviewed_requirement"}
    assert protection_control["external_protection_coverage"]["status"] == "COMPLETE"

    serial_label_fault = reports["serial_label_unmapped"]
    assert serial_label_fault["status"] == "REVIEW"
    serial_label_findings = {
        finding["rule_id"]: finding for finding in serial_label_fault["findings"]
    }
    assert "bus.serial_unmapped_peer" in serial_label_findings
    assert serial_label_findings["bus.serial_unmapped_peer"]["evidence"]["discovery_basis"] == [
        "net_label"
    ]
    serial_label_mapped_control = reports["serial_label_mapped_control"]
    assert serial_label_mapped_control["status"] == "REVIEW"
    assert [finding["rule_id"] for finding in serial_label_mapped_control["findings"]] == [
        "connector.no_connected_return"
    ], "the exact serial map clears its candidate but must preserve independent pin-role review"
    serial_reference_fault = reports["serial_reference_fault"]
    assert serial_reference_fault["status"] == "REVIEW"
    serial_reference_findings = [
        finding
        for finding in serial_reference_fault["findings"]
        if finding["rule_id"] == "bus.serial_peer_reference_review"
    ]
    assert len(serial_reference_findings) == 1
    assert serial_reference_findings[0]["subject"] == "J1 / U1: serial reference-domain review"
    serial_reference_control = reports["serial_reference_control"]
    assert "bus.serial_peer_reference_review" not in {
        finding["rule_id"] for finding in serial_reference_control["findings"]
    }, "the all-common UART control must clear this heuristic without erasing other review"
    serial_bond_fault = reports["serial_reference_bond_fault"]
    serial_bond_control = reports["serial_reference_bond_control"]
    fault_reference_check = next(
        item for item in serial_bond_fault if item["id"] == "serial/console-link/reference"
    )
    control_reference_check = next(
        item for item in serial_bond_control if item["id"] == "serial/console-link/reference"
    )
    assert fault_reference_check["status"] == "FAIL"
    assert "R3.2 is on FLOATING_GND" in fault_reference_check["detail"]
    assert control_reference_check["status"] == "PASS"
    serial_label_reference_fault = reports["serial_label_reference_fault"]
    serial_label_reference_findings = tuple(
        finding
        for finding in serial_label_reference_fault["findings"]
        if finding["rule_id"] == "bus.serial_peer_reference_review"
    )
    assert len(serial_label_reference_findings) == 1
    assert serial_label_reference_findings[0]["evidence"]["discovery_basis"] == ["net_label"]
    assert "bus.serial_peer_reference_review" not in {
        finding["rule_id"] for finding in reports["serial_label_reference_control"]["findings"]
    }
    spi_voltage_review = reports["spi_peer_voltage_unmapped"]
    assert spi_voltage_review["status"] == "REVIEW"
    assert "bus.spi_peer_voltage_review" in {
        finding["rule_id"] for finding in spi_voltage_review["findings"]
    }
    spi_voltage_control = reports["spi_peer_voltage_mapped_control"]
    assert "bus.spi_peer_voltage_review" not in {
        finding["rule_id"] for finding in spi_voltage_control["findings"]
    }, "the exact complete voltage map must suppress only the SPI voltage prompt"
    serial_voltage_review = reports["serial_peer_voltage_unmapped"]
    assert serial_voltage_review["status"] == "REVIEW"
    assert "bus.serial_peer_voltage_review" in {
        finding["rule_id"] for finding in serial_voltage_review["findings"]
    }
    serial_voltage_control = reports["serial_peer_voltage_mapped_control"]
    assert "bus.serial_peer_voltage_review" not in {
        finding["rule_id"] for finding in serial_voltage_control["findings"]
    }, "the exact complete voltage map must suppress only the UART voltage prompt"
    can_fault = reports["can_peer_fault"]
    assert can_fault["status"] == "REVIEW"
    assert "bus.can_peer_assignment_divergence" in {
        finding["rule_id"] for finding in can_fault["findings"]
    }
    can_control = reports["can_peer_control"]
    assert "bus.can_peer_assignment_divergence" not in {
        finding["rule_id"] for finding in can_control["findings"]
    }
    assert can_fault["netlist_sha256"] != can_control["netlist_sha256"], (
        "fault and control reports must bind their distinct typed-netlist inputs"
    )
    usb_path_fault = reports["usb_data_path_series_fault"]
    usb_path_control = reports["usb_data_path_series_control"]
    usb_direct_control = reports["usb_data_path_direct_topology_control"]
    usb_path_fault_ids = {item["rule_id"] for item in usb_path_fault["findings"]}
    assert usb_path_fault["status"] == "REVIEW"
    assert usb_path_fault_ids == {"bus.usb_data_path_mismatch"}
    usb_path_finding = usb_path_fault["findings"][0]
    assert usb_path_finding["subject"] == "usb-port-1: USB D+ path"
    assert "R1 is absent" in usb_path_finding["evidence"]["issues"][0]
    usb_path_run = next(
        item
        for item in usb_path_fault["mapped_check_runs"]
        if item["rule_id"] == "bus.usb_data_path_mismatch"
    )
    usb_control_run = next(
        item
        for item in usb_path_control["mapped_check_runs"]
        if item["rule_id"] == "bus.usb_data_path_mismatch"
    )
    assert usb_path_run["status"] == "EVALUATED"
    assert usb_path_run["requirement_count"] == 1
    assert usb_path_run["finding_count"] == 1
    assert usb_control_run["status"] == "EVALUATED"
    assert usb_control_run["finding_count"] == 0
    assert usb_path_run["map_sha256"] == usb_control_run["map_sha256"]
    assert usb_path_fault["netlist_sha256"] != usb_path_control["netlist_sha256"]
    assert usb_path_control["status"] == "PASS"
    assert usb_path_control["findings"] == []
    assert usb_direct_control["status"] == "REVIEW"
    assert {item["rule_id"] for item in usb_direct_control["findings"]} == {
        "mcu.stm32_cubemx_pin_map",
        "signal.named_pair_without_reviewed_requirement",
    }, "the USB path map must preserve independent firmware-map and PCB-pair review prompts"
    assert "bus.usb_data_path_mismatch" not in {
        item["rule_id"] for item in usb_direct_control["findings"]
    }
    usb_bond_fault = reports["usb_reference_bond_fault"]
    assert usb_bond_fault["status"] == "REVIEW"
    assert {item["rule_id"] for item in usb_bond_fault["findings"]} == {
        "bus.usb_data_path_mismatch"
    }
    bond_finding = usb_bond_fault["findings"][0]
    assert bond_finding["subject"] == "usb-port-1: USB reference path"
    assert any("R3.2 is on FLOATING_GND" in issue for issue in bond_finding["evidence"]["issues"])
    assert reports["usb_reference_bond_control"]["status"] == "PASS"
    assert reports["usb_reference_bond_control"]["findings"] == []
    usb_multiport_fault = reports["usb_multiport_peer_fault"]
    usb_fault_coverage = usb_multiport_fault["usb_peer_reference_coverage"]
    assert usb_fault_coverage["status"] == "EVALUATED"
    assert usb_fault_coverage["recognized_connector_group_count"] == 2
    assert usb_fault_coverage["supported_connector_group_count"] == 2
    assert usb_fault_coverage["recognized_phy_group_count"] == 2
    assert usb_fault_coverage["supported_phy_group_count"] == 2
    assert usb_fault_coverage["supported_data_path_count"] == 2
    assert usb_fault_coverage["separate_reference_path_count"] == 2
    assert usb_fault_coverage["candidate_group_count"] == 2
    multiport_findings = tuple(
        finding
        for finding in usb_multiport_fault["findings"]
        if finding["rule_id"] == "bus.usb_peer_reference_review"
    )
    assert tuple(
        (finding["subject"], finding["evidence"]["USB_port_group"])
        for finding in multiport_findings
    ) == (
        ("J1 / U1: USB reference-domain review (port 1)", ["1"]),
        ("J2 / U1: USB reference-domain review (port 2)", ["2"]),
    )
    assert "bus.usb_peer_reference_review" not in {
        finding["rule_id"] for finding in reports["usb_multiport_peer_control"]["findings"]
    }
    usb_control_coverage = reports["usb_multiport_peer_control"]["usb_peer_reference_coverage"]
    assert usb_control_coverage["common_reference_path_count"] == 2
    assert usb_control_coverage["separate_reference_path_count"] == 0
    assert usb_control_coverage["candidate_group_count"] == 0
    header_boundary = reports["header_only_spi_uart_boundary"]
    assert {
        item["rule_id"]: (
            item["status"],
            item["recognized_endpoint_count"],
            item["direct_peer_link_count"],
            item["voltage_comparison_count"],
            item["candidate_group_count"],
        )
        for item in header_boundary["digital_peer_voltage_coverage"]
    } == {
        "bus.spi_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
        "bus.serial_peer_voltage_review": ("NO_SUPPORTED_ENDPOINTS", 0, 0, 0, 0),
    }
    assert not {"bus.spi_peer_voltage_review", "bus.serial_peer_voltage_review"} & {
        finding["rule_id"] for finding in header_boundary["findings"]
    }
    stm32_fault = reports["stm32_pin_map_fault"]
    assert stm32_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in stm32_fault["findings"]} == {
        "mcu.stm32_cubemx_pin_map"
    }
    stm32_fault_coverage = stm32_fault["stm32_pin_map_coverage"]
    stm32_control = reports["stm32_pin_map_control"]
    assert stm32_control["status"] == "PASS"
    assert stm32_control["findings"] == []
    stm32_control_coverage = stm32_control["stm32_pin_map_coverage"]
    assert stm32_fault_coverage["status"] == "COMPLETE"
    assert stm32_fault_coverage["mapped_pin_count"] == 3
    assert stm32_fault_coverage["excluded_pin_count"] == 1
    assert stm32_fault_coverage["map_sha256"] == stm32_control_coverage["map_sha256"]
    assert (
        stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"]
        != stm32_control_coverage["ioc_source_hashes"]["firmware/controller.ioc"]
    )
    assert (
        stm32_fault["source_hashes"]["firmware/controller.ioc"]
        == stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"]
    )
    assert (
        stm32_control["source_hashes"]["firmware/controller.ioc"]
        == stm32_control_coverage["ioc_source_hashes"]["firmware/controller.ioc"]
    )
    stm32_finding_evidence = stm32_fault["findings"][0]["evidence"]
    assert stm32_finding_evidence["ioc_sha256"] == [
        stm32_fault_coverage["ioc_source_hashes"]["firmware/controller.ioc"]
    ]
    assert stm32_finding_evidence["map_sha256"] == [stm32_fault_coverage["map_sha256"]]
