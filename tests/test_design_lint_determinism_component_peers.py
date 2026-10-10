"""Component Peers hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


def test_component_peer_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("component_peers", "connectors"))
    power_input_fault = reports["generic_power_input_fault"]
    assert power_input_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in power_input_fault["findings"]} == {
        "connector.unconnected_power_input"
    }
    assert reports["generic_power_input_control"]["status"] == "PASS"
    assert reports["generic_power_input_control"]["findings"] == []
    component_power_input_fault = reports["generic_component_power_input_fault"]
    assert component_power_input_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in component_power_input_fault["findings"]} == {
        "component.unconnected_power_input"
    }
    component_power_input_control = reports["generic_component_power_input_control"]
    assert component_power_input_control["status"] == "PASS"
    assert component_power_input_control["findings"] == []
    peer_input_fault = reports["peer_signal_input_fault"]
    assert peer_input_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in peer_input_fault["findings"]} == {
        "component.peer_signal_input_unconnected"
    }
    assert reports["peer_signal_input_control"]["status"] == "PASS"
    assert reports["peer_signal_input_control"]["findings"] == []
    peer_signal_output_fault = reports["peer_signal_output_fault"]
    assert peer_signal_output_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in peer_signal_output_fault["findings"]} == {
        "component.peer_signal_output_unconnected"
    }
    peer_signal_output_control = reports["peer_signal_output_control"]
    assert peer_signal_output_control["status"] == "PASS"
    assert peer_signal_output_control["findings"] == []
    for name, expected_count in (
        ("peer_signal_output_fault", 1),
        ("peer_signal_output_control", 0),
    ):
        report = reports[name]
        coverage = next(
            item
            for item in report["component_peer_pin_coverage"]
            if item["rule_id"] == "component.peer_signal_output_unconnected"
        )
        assert coverage["status"] == "EVALUATED"
        assert coverage["netlist_sha256"] == report["netlist_sha256"]
        assert coverage["candidate_group_count"] == expected_count
        assert coverage["finding_count"] == expected_count
        assert coverage["suppressed_candidate_count"] == 0
    for kind, rule_id in (
        ("signal_output", "component.peer_signal_output_unconnected"),
        ("signal_input", "component.peer_signal_input_unconnected"),
        ("bidirectional", "component.peer_bidirectional_pin_unconnected"),
    ):
        fault = reports[f"peer_{kind}_part_id_fault"]
        control = reports[f"peer_{kind}_part_id_control"]
        assert fault["status"] == "REVIEW"
        assert {finding["rule_id"] for finding in fault["findings"]} == {rule_id}
        finding = next(item for item in fault["findings"] if item["rule_id"] == rule_id)
        assert finding["evidence"]["peer_group_basis"] == ["part_id"]
        assert finding["evidence"]["peer_group_identity"] == ["SYNTHETIC-PEER-MODULE"]
        assert finding["evidence"]["unassigned_pins"] == ["U2.2"]
        assert control["status"] == "PASS"
        assert control["findings"] == []
        for report, expected_count in ((fault, 1), (control, 0)):
            coverage = next(
                item for item in report["component_peer_pin_coverage"] if item["rule_id"] == rule_id
            )
            assert coverage["status"] == "EVALUATED"
            assert coverage["netlist_sha256"] == report["netlist_sha256"]
            assert coverage["exact_symbol_peer_group_count"] == 0
            assert coverage["part_id_peer_group_count"] == 1
            assert coverage["candidate_group_count"] == expected_count
            assert coverage["finding_count"] == expected_count
            assert coverage["suppressed_candidate_count"] == 0
    peer_bidirectional_fault = reports["peer_bidirectional_fault"]
    assert peer_bidirectional_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in peer_bidirectional_fault["findings"]} == {
        "component.peer_bidirectional_pin_unconnected"
    }
    assert reports["peer_bidirectional_control"]["status"] == "PASS"
    assert reports["peer_bidirectional_control"]["findings"] == []
    for name, expected_count in (
        ("peer_bidirectional_fault", 1),
        ("peer_bidirectional_control", 0),
    ):
        report = reports[name]
        coverage = next(
            item
            for item in report["component_peer_pin_coverage"]
            if item["rule_id"] == "component.peer_bidirectional_pin_unconnected"
        )
        assert coverage["status"] == "EVALUATED"
        assert coverage["netlist_sha256"] == report["netlist_sha256"]
        assert coverage["candidate_group_count"] == expected_count
        assert coverage["finding_count"] == expected_count
        assert coverage["suppressed_candidate_count"] == 0
    peer_power_output_fault = reports["peer_power_output_part_id_fault"]
    assert peer_power_output_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in peer_power_output_fault["findings"]} == {
        "component.peer_power_output_unconnected"
    }
    peer_power_output_fault_coverage = next(
        item
        for item in peer_power_output_fault["component_peer_pin_coverage"]
        if item["rule_id"] == "component.peer_power_output_unconnected"
    )
    assert peer_power_output_fault_coverage["status"] == "EVALUATED"
    assert (
        peer_power_output_fault_coverage["netlist_sha256"]
        == peer_power_output_fault["netlist_sha256"]
    )
    assert peer_power_output_fault_coverage["part_id_peer_group_count"] == 1
    assert peer_power_output_fault_coverage["part_id_candidate_group_count"] == 1
    assert (
        peer_power_output_fault_coverage["part_id_incomplete_component_identity_group_count"] == 0
    )
    assert peer_power_output_fault_coverage["candidate_group_count"] == 1
    assert peer_power_output_fault_coverage["finding_count"] == 1
    assert peer_power_output_fault_coverage["suppressed_candidate_count"] == 0
    peer_power_output_control = reports["peer_power_output_part_id_control"]
    assert peer_power_output_control["status"] == "PASS"
    assert peer_power_output_control["findings"] == []
    peer_power_output_control_coverage = next(
        item
        for item in peer_power_output_control["component_peer_pin_coverage"]
        if item["rule_id"] == "component.peer_power_output_unconnected"
    )
    assert peer_power_output_control_coverage["status"] == "EVALUATED"
    assert peer_power_output_control_coverage["part_id_candidate_group_count"] == 1
    assert peer_power_output_control_coverage["candidate_group_count"] == 0
    assert peer_power_output_control_coverage["finding_count"] == 0
    peer_power_output_incomplete = reports["peer_power_output_part_id_incomplete_identity"]
    assert peer_power_output_incomplete["status"] == "PASS"
    assert peer_power_output_incomplete["findings"] == []
    for coverage in peer_power_output_incomplete["component_peer_pin_coverage"]:
        assert coverage["status"] == "INCOMPLETE_COMPONENT_IDENTITY"
        assert coverage["netlist_sha256"] == peer_power_output_incomplete["netlist_sha256"]
        assert coverage["part_id_candidate_group_count"] == 1
        assert coverage["part_id_peer_group_count"] == 0
        assert coverage["part_id_incomplete_component_identity_group_count"] == 1
        assert coverage["part_id_incomplete_component_identity_references"] == ["U1", "U2"]
    for name, expected_candidate_count, expected_deduplicated_count in (
        ("peer_power_output_part_id_dedup_fault", 1, 1),
        ("peer_power_output_part_id_dedup_control", 0, 0),
    ):
        report = reports[name]
        findings = [
            item
            for item in report["findings"]
            if item["rule_id"] == "component.peer_power_output_unconnected"
        ]
        assert report["status"] == ("REVIEW" if expected_candidate_count else "PASS")
        assert len(findings) == expected_candidate_count
        if findings:
            assert findings[0]["evidence"]["peer_group_basis"] == ["exact_symbol"]
            assert findings[0]["evidence"]["unassigned_pins"] == ["U2.2"]
        coverage = next(
            item
            for item in report["component_peer_pin_coverage"]
            if item["rule_id"] == "component.peer_power_output_unconnected"
        )
        assert coverage["status"] == "EVALUATED"
        assert coverage["netlist_sha256"] == report["netlist_sha256"]
        assert coverage["exact_symbol_peer_group_count"] == 1
        assert coverage["part_id_peer_group_count"] == 1
        assert coverage["candidate_group_count"] == expected_candidate_count
        assert coverage["deduplicated_candidate_group_count"] == expected_deduplicated_count
        assert coverage["finding_count"] == expected_candidate_count
        assert coverage["suppressed_candidate_count"] == 0
    peer_power_assignment_fault = reports["peer_power_assignment_part_id_fault"]
    assert peer_power_assignment_fault["status"] == "REVIEW"
    peer_power_assignment_findings = [
        finding
        for finding in peer_power_assignment_fault["findings"]
        if finding["rule_id"] == "component.peer_power_pin_assignment_divergence"
    ]
    assert len(peer_power_assignment_findings) == 2
    assert {
        tuple(finding["evidence"]["peer_role"]) for finding in peer_power_assignment_findings
    } == {("ground/return",), ("supply",)}
    assert all(
        finding["evidence"]["peer_identity_basis"] == ["part_id"]
        and finding["evidence"]["peer_identity"] == ["SYNTHETIC-POWER-001"]
        for finding in peer_power_assignment_findings
    )
    peer_power_assignment_control = reports["peer_power_assignment_part_id_control"]
    assert peer_power_assignment_control["status"] == "REVIEW"
    assert "component.peer_power_pin_assignment_divergence" not in {
        finding["rule_id"] for finding in peer_power_assignment_control["findings"]
    }
