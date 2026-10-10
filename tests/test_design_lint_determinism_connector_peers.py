"""Connector Peers hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
]


def test_connector_peer_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("components", "connectors", "returns"))
    alias_fault = reports["connector_part_id_alias_open_fault"]
    alias_split = reports["connector_part_id_alias_split_fault"]
    alias_control = reports["connector_part_id_alias_common_control"]
    assert alias_fault["status"] == "REVIEW"
    alias_findings = [
        finding
        for finding in alias_fault["findings"]
        if finding["rule_id"] == "connector.peer_pin_assignment_outlier"
    ]
    assert len(alias_findings) == 1
    assert alias_findings[0]["evidence"]["peer_identity_basis"] == ["part_id"]
    assert alias_findings[0]["evidence"]["outlier_pins"] == ["J2.2"]
    alias_coverage = alias_fault["connector_peer_pin_coverage"]["part_id_alias_coverage"]
    assert alias_coverage["status"] == "EVALUATED"
    assert alias_coverage["candidate_group_count"] == 1
    assert alias_coverage["eligible_peer_group_count"] == 1
    assert alias_coverage["open_assignment_pin_group_count"] == 1
    assert alias_coverage["outlier_finding_count"] == 1
    split_findings = [
        finding
        for finding in alias_split["findings"]
        if finding["rule_id"] == "connector.peer_pin_assignment_divergence"
    ]
    assert alias_split["status"] == "REVIEW"
    assert len(split_findings) == 1
    assert split_findings[0]["evidence"]["peer_identity_basis"] == ["part_id"]
    split_coverage = alias_split["connector_peer_pin_coverage"]["part_id_alias_coverage"]
    assert split_coverage["different_assignment_pin_group_count"] == 1
    assert split_coverage["outlier_finding_count"] == 0
    assert split_coverage["divergence_finding_count"] == 1
    assert alias_control["status"] == "PASS"
    assert alias_control["findings"] == []
    assert (
        alias_control["connector_peer_pin_coverage"]["part_id_alias_coverage"][
            "common_assignment_pin_group_count"
        ]
        == 2
    )
    peer_pin_fault = reports["peer_pin_fault"]
    assert peer_pin_fault["status"] == "REVIEW"
    assert "connector.peer_pin_assignment_outlier" in {
        finding["rule_id"] for finding in peer_pin_fault["findings"]
    }
    assert reports["peer_pin_control"]["status"] == "PASS"
    assert reports["peer_pin_control"]["findings"] == []
    for peer_report, expected_outliers, expected_common, expected_open in (
        (peer_pin_fault, 1, 1, 1),
        (reports["peer_pin_control"], 0, 2, 0),
    ):
        peer_coverage = peer_report["connector_peer_pin_coverage"]
        assert peer_coverage["status"] == "EVALUATED"
        assert peer_coverage["netlist_sha256"] == peer_report["netlist_sha256"]
        assert peer_coverage["connector_candidate_count"] == 3
        assert peer_coverage["exact_symbol_peer_group_count"] == 1
        assert peer_coverage["exact_symbol_pin_group_count"] == 2
        assert (
            peer_coverage["exact_symbol_pin_groups_with_common_assignment_count"] == expected_common
        )
        assert peer_coverage["exact_symbol_pin_groups_with_open_assignment_count"] == expected_open
        assert peer_coverage["peer_pin_outlier_finding_count"] == expected_outliers
    separate_peer_scopes = reports["connector_peer_scope_separate"]
    separate_peer_rule_ids = {finding["rule_id"] for finding in separate_peer_scopes["findings"]}
    assert "connector.repeated_pin_function" in separate_peer_rule_ids
    assert "connector.peer_pin_assignment_divergence" not in separate_peer_rule_ids
    shared_peer_scopes = reports["connector_peer_scope_shared"]
    shared_peer_divergences = [
        finding
        for finding in shared_peer_scopes["findings"]
        if finding["rule_id"] == "connector.peer_pin_assignment_divergence"
    ]
    assert len(shared_peer_divergences) == 2
    assert all(
        finding["evidence"]["peer_assignment_group"] == ["uart-ports"]
        and len(finding["evidence"]["peer_assignment_basis"]) == 2
        for finding in shared_peer_divergences
    )
    unlisted_separate = reports["unlisted_peer_scope_separate_fault"]
    unlisted_separate_findings = {
        finding["rule_id"]: finding for finding in unlisted_separate["findings"]
    }
    assert unlisted_separate["status"] == "REVIEW"
    assert set(unlisted_separate_findings) == {"connector.repeated_pin_function"}
    assert {
        pin: unlisted_separate_findings["connector.repeated_pin_function"]["evidence"][pin]
        for pin in ("J1.2", "J2.2", "J3.2")
    } == {"J1.2": ["RETURN_A"], "J2.2": ["RETURN_B"], "J3.2": ["RETURN_C"]}
    unlisted_shared = reports["unlisted_peer_scope_shared_fault"]
    unlisted_shared_findings = {
        finding["rule_id"]: finding for finding in unlisted_shared["findings"]
    }
    assert unlisted_shared["status"] == "REVIEW"
    assert set(unlisted_shared_findings) == {
        "connector.repeated_pin_function",
        "connector.peer_pin_assignment_divergence",
    }
    unlisted_divergence = unlisted_shared_findings["connector.peer_pin_assignment_divergence"]
    assert unlisted_divergence["evidence"]["peer_assignment_group"] == ["uart-peers"]
    assert len(unlisted_divergence["evidence"]["peer_assignment_basis"]) == 3
    assert reports["unlisted_peer_scope_shared_control"]["status"] == "PASS"
    assert reports["unlisted_peer_scope_shared_control"]["findings"] == []
    mapped_return_fault = reports["mapped_return_fault"]
    assert mapped_return_fault["status"] == "REVIEW"
    mapped_return_findings = {
        finding["rule_id"]: finding for finding in mapped_return_fault["findings"]
    }
    assert "connector.repeated_pin_function" in mapped_return_findings
    assert mapped_return_findings["connector.repeated_pin_function"]["evidence"][
        "role_classification_sources"
    ] == [
        "J1.3: project interface catalog role=return; native symbol function=GND",
        "J2.3: project interface catalog role=return; native symbol function=Pin_3",
    ]
    assert reports["mapped_return_control"]["status"] == "PASS"
    assert reports["mapped_return_control"]["findings"] == []
    mapped_supply_fault = reports["mapped_supply_open_peer_fault"]
    assert mapped_supply_fault["status"] == "REVIEW"
    assert mapped_supply_fault["connector_coverage"]["status"] == "COMPLETE"
    mapped_supply_finding = next(
        finding
        for finding in mapped_supply_fault["findings"]
        if finding["rule_id"] == "connector.repeated_pin_function"
    )
    assert mapped_supply_finding["evidence"]["J2.5"] == []
    assert mapped_supply_finding["evidence"]["reviewed_voltage_domain"] == ["external-5v"]
    assert {finding["rule_id"] for finding in mapped_supply_fault["findings"]} == {
        "connector.repeated_pin_function"
    }, "the role-aware peer finding reports the open contact without a duplicate prompt"
    assert reports["mapped_supply_common_control"]["status"] == "PASS"
    assert reports["mapped_supply_common_control"]["findings"] == []
    contact_rating_fault = reports["connector_contact_rating_over_limit"]
    contact_rating_control = reports["connector_contact_rating_boundary_control"]
    assert contact_rating_fault["netlist_sha256"] == contact_rating_control["netlist_sha256"]
    assert (
        contact_rating_fault["requirements_sha256"] != contact_rating_control["requirements_sha256"]
    )
    fault_checks = {
        check["id"].rsplit("/", maxsplit=1)[-1]: check for check in contact_rating_fault["checks"]
    }
    control_checks = {
        check["id"].rsplit("/", maxsplit=1)[-1]: check for check in contact_rating_control["checks"]
    }
    assert fault_checks["identity"]["status"] == "PASS"
    assert fault_checks["assignment"]["status"] == "PASS"
    assert fault_checks["utilization"]["status"] == "FAIL"
    assert fault_checks["utilization"]["observed"] == pytest.approx(0.805, rel=0.0, abs=5e-08)
    assert control_checks["utilization"]["status"] == "PASS"
    assert control_checks["utilization"]["observed"] == pytest.approx(0.8, rel=0.0, abs=5e-08)
    mosfet_fault = reports["mosfet_stress_q2_over_limit"]
    mosfet_control = reports["mosfet_stress_multi_device_control"]
    assert mosfet_fault["netlist_sha256"] == mosfet_control["netlist_sha256"]
    assert mosfet_fault["requirements_sha256"] != mosfet_control["requirements_sha256"]
    mosfet_fault_statuses = {check["id"]: check["status"] for check in mosfet_fault["checks"]}
    mosfet_control_statuses = {check["id"]: check["status"] for check in mosfet_control["checks"]}
    assert {
        check_id
        for check_id, status in mosfet_fault_statuses.items()
        if status != mosfet_control_statuses[check_id]
    } == {"mosfet-stress/switch-q2/state-on/vds"}, (
        "the authored Q2 drain envelope changes only Q2 on-state VDS coverage"
    )
    assert mosfet_fault_statuses["mosfet-stress/switch-q2/state-on/vds"] == "FAIL"
    assert mosfet_fault_statuses["mosfet-stress/switch-q1/state-on/vds"] == "PASS"
    assert all(status == "PASS" for status in mosfet_control_statuses.values())
    partial_peer_map = reports["partial_mapped_peer_pin_fault"]
    assert partial_peer_map["status"] == "REVIEW"
    assert partial_peer_map["connector_coverage"]["status"] == "UNDECLARED"
    assert (
        next(
            entry["status"]
            for entry in partial_peer_map["connector_coverage"]["entries"]
            if entry["reference"] == "J3"
        )
        == "UNDECLARED"
    )
    partial_peer_findings = {
        finding["rule_id"]: finding for finding in partial_peer_map["findings"]
    }
    assert "connector.repeated_pin_function" in partial_peer_findings
    generic_peer_finding = partial_peer_findings["connector.peer_pin_assignment_outlier"]
    assert generic_peer_finding["evidence"]["outlier_pins"] == ["J2.1"]
    assert generic_peer_finding["evidence"]["J3.1"] == ["SUPPLY_A"]
    complete_peer_map = reports["complete_mapped_peer_pin_control"]
    assert complete_peer_map["connector_coverage"]["status"] == "COMPLETE"
    complete_peer_rule_ids = {finding["rule_id"] for finding in complete_peer_map["findings"]}
    assert "connector.repeated_pin_function" in complete_peer_rule_ids
    assert "connector.peer_pin_assignment_outlier" not in complete_peer_rule_ids, (
        "complete role coverage may replace the overlapping generic peer warning"
    )
    assert reports["common_peer_pin_control"]["status"] == "PASS"
