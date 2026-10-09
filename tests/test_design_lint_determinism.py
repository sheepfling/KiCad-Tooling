"""Cross-process determinism checks for source-bound lint reports."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_high_risk_reports_ignore_python_hash_seed() -> None:
    repository = Path(__file__).parents[1]
    probe = Path(__file__).with_name("hashseed_probe.py")
    command = [
        sys.executable,
        "-I",
        "-m",
        "pytest",
        "-q",
        "-s",
        "--override-ini=python_files=hashseed_probe.py",
        str(probe),
    ]
    outputs: list[str] = []
    hash_markers: set[int] = set()
    for _process_index in range(3):
        environment = os.environ.copy()
        environment.pop("PYTHONHASHSEED", None)
        result = subprocess.run(
            command,
            cwd=repository,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"hash-seed probe failed:\n{result.stdout}\n{result.stderr}"
        payloads = [
            line.removeprefix("DESIGN_LINT_HASHSEED_REPORTS=")
            for line in result.stdout.splitlines()
            if line.startswith("DESIGN_LINT_HASHSEED_REPORTS=")
        ]
        assert len(payloads) == 1, result.stdout
        payload = json.loads(payloads[0])
        assert payload["hash_randomization"] == 1
        hash_markers.add(payload["hash_marker"])
        outputs.append(json.dumps(payload["reports"], ensure_ascii=False, separators=(",", ":")))

    assert len(hash_markers) == 3, "probe processes did not use distinct hash secrets"
    digests = tuple(hashlib.sha256(output.encode("utf-8")).hexdigest() for output in outputs)
    assert digests[0] == digests[1], "full report JSON changed across hash seeds"
    assert digests[1] == digests[2], "full report JSON changed across hash seeds"

    reports = json.loads(outputs[0])
    parsed_pin_metadata = reports["parsed_netlist_pin_metadata"]
    for metadata in parsed_pin_metadata.values():
        keys = [pin for pin, _value in metadata]
        assert len(keys) == 24
        assert keys == sorted(keys)
    assert dict(parsed_pin_metadata["pin_functions"]) == {
        f"J1.{number}": f"FUNCTION_{number}" for number in range(1, 25)
    }
    assert dict(parsed_pin_metadata["pin_electrical_types"]) == {
        f"J1.{number}": "passive" for number in range(1, 25)
    }
    fault = reports["fault"]
    assert fault["status"] == "REVIEW"
    assert {"connector.repeated_pin_function", "net.numbered_returns"} <= {
        finding["rule_id"] for finding in fault["findings"]
    }
    assert reports["common_control"]["status"] == "PASS"
    assert reports["common_control"]["findings"] == []

    suffix_fault = reports["letter_suffixed_unindexed_return_fault"]
    assert suffix_fault["status"] == "REVIEW"
    assert "net.return_labels_without_pin_roles" in {
        finding["rule_id"] for finding in suffix_fault["findings"]
    }
    suffix_numbered_fault = reports["letter_suffixed_numbered_return_fault"]
    assert suffix_numbered_fault["status"] == "REVIEW"
    assert "net.numbered_returns" in {
        finding["rule_id"] for finding in suffix_numbered_fault["findings"]
    }
    suffix_role_control = reports["letter_suffixed_return_roles_control"]
    assert suffix_role_control["status"] == "PASS"
    assert suffix_role_control["findings"] == []

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
        == (peer_power_output_fault["netlist_sha256"])
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

    split_common = reports["db9_split_against_common_requirement"]
    split_isolated = reports["db9_split_against_isolated_requirement"]
    common_common = reports["db9_common_against_common_requirement"]
    common_isolated = reports["db9_common_against_isolated_requirement"]
    assert split_common["netlist_sha256"] == split_isolated["netlist_sha256"]
    assert split_common["requirements_sha256"] != split_isolated["requirements_sha256"]
    assert (
        split_common["connectivity_requirements_sha256"]
        != split_isolated["connectivity_requirements_sha256"]
    )
    assert common_common["netlist_sha256"] == common_isolated["netlist_sha256"]
    assert common_common["requirements_sha256"] != common_isolated["requirements_sha256"]
    assert (
        common_common["connectivity_requirements_sha256"]
        != common_isolated["connectivity_requirements_sha256"]
    )
    grounding_statuses = {
        name: {check["id"]: check["status"] for check in result["checks"]}
        for name, result in (
            ("split_common", split_common),
            ("split_isolated", split_isolated),
            ("common_common", common_common),
            ("common_isolated", common_isolated),
        )
    }
    assert grounding_statuses["split_common"] == {
        "grounding/COMMON_RETURN": "FAIL",
        "grounding/return-net-review": "FAIL",
        "grounding/component-coverage": "PASS",
    }
    assert grounding_statuses["split_isolated"] == {
        **{f"grounding/RETURN_PORT_{reference}": "PASS" for reference in range(1, 5)},
        "grounding/return-net-review": "PASS",
        "grounding/component-coverage": "PASS",
    }
    assert grounding_statuses["common_common"] == {
        "grounding/COMMON_RETURN": "PASS",
        "grounding/component-coverage": "PASS",
    }
    assert grounding_statuses["common_isolated"] == {
        **{f"grounding/RETURN_PORT_{reference}": "FAIL" for reference in range(1, 5)},
        "grounding/component-coverage": "PASS",
    }
    pin_connectivity_statuses = {
        name: {check["id"]: check["status"] for check in result["pin_connectivity_checks"]}
        for name, result in (
            ("split_common", split_common),
            ("split_isolated", split_isolated),
            ("common_common", common_common),
            ("common_isolated", common_isolated),
        )
    }
    assert pin_connectivity_statuses["split_common"] == {
        "pin-connectivity/db9-common-return": "FAIL"
    }
    assert pin_connectivity_statuses["split_isolated"] == {
        f"pin-connectivity/db9-{reference}-isolated-return": "PASS" for reference in range(1, 5)
    }
    assert pin_connectivity_statuses["common_common"] == {
        "pin-connectivity/db9-common-return": "PASS"
    }
    assert pin_connectivity_statuses["common_isolated"] == {
        f"pin-connectivity/db9-{reference}-isolated-return": "FAIL" for reference in range(1, 5)
    }
    inventory_results = reports["unconnected_pin_inventory"]
    assert (
        inventory_results["missing_inventory"]["netlist_sha256"]
        != inventory_results["complete_inventory_control"]["netlist_sha256"]
    )
    assert inventory_results["missing_inventory"]["checks"][0]["status"] == "FAIL"
    assert (
        "missing symbol pin inventory=['J1']"
        in inventory_results["missing_inventory"]["checks"][0]["detail"]
    )
    assert inventory_results["complete_inventory_control"]["checks"][0]["status"] == "PASS"

    diode_fault = reports["diode_fault"]
    assert diode_fault["status"] == "REVIEW"
    assert "component.two_pin_diode_same_net" in {
        finding["rule_id"] for finding in diode_fault["findings"]
    }
    assert reports["diode_control"]["status"] == "PASS"
    assert reports["diode_control"]["findings"] == []
    crystal_fault = reports["crystal_fault"]
    assert crystal_fault["status"] == "REVIEW"
    assert (
        sum(
            finding["rule_id"] == "component.two_pin_crystal_same_net"
            for finding in crystal_fault["findings"]
        )
        == 2
    )
    assert reports["crystal_control"]["status"] == "PASS"
    assert reports["crystal_control"]["findings"] == []
    fuse_fault = reports["fuse_fault"]
    assert fuse_fault["status"] == "REVIEW"
    assert "component.two_pin_fuse_same_net" in {
        finding["rule_id"] for finding in fuse_fault["findings"]
    }
    assert reports["fuse_control"]["status"] == "PASS"
    assert reports["fuse_control"]["findings"] == []
    ferrite_fault = reports["ferrite_fault"]
    assert ferrite_fault["status"] == "REVIEW"
    assert (
        sum(
            finding["rule_id"] == "component.two_pin_ferrite_same_net"
            for finding in ferrite_fault["findings"]
        )
        == 2
    )
    assert reports["ferrite_control"]["status"] == "PASS"
    assert reports["ferrite_control"]["findings"] == []
    switch_fault = reports["switch_fault"]
    assert switch_fault["status"] == "REVIEW"
    assert {finding["rule_id"] for finding in switch_fault["findings"]} == {
        "component.two_pin_switch_same_net"
    }
    assert reports["switch_control"]["status"] == "PASS"
    assert reports["switch_control"]["findings"] == []
    for report_name in (
        "led_output_direct_fault",
        "led_output_parallel_resistor_fault",
    ):
        led_fault = reports[report_name]
        assert led_fault["status"] == "REVIEW"
        assert "component.led_directly_driven_from_output" in {
            finding["rule_id"] for finding in led_fault["findings"]
        }
    led_series = reports["led_output_series_control"]
    assert led_series["status"] == "REVIEW"
    led_series_rule_ids = {finding["rule_id"] for finding in led_series["findings"]}
    assert "component.led_directly_driven_from_output" not in led_series_rule_ids
    assert led_series_rule_ids == {"net.return_labels_without_pin_roles"}
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
    assert reports["common_peer_pin_control"]["findings"] == []

    decoupling_fault = reports["pcb_decoupling_distance_fault"]
    assert decoupling_fault["status"] == "REVIEW"
    assert decoupling_fault["pcb_decoupling"]["status"] == "INCOMPLETE"
    assert "pcb.decoupling_proximity" in {
        finding["rule_id"] for finding in decoupling_fault["findings"]
    }
    assert (
        decoupling_fault["pcb_decoupling"]["entries"][0]["candidates"][0]["distance_nm"] == 100001
    )
    decoupling_control = reports["pcb_decoupling_distance_control"]
    assert decoupling_control["status"] == "PASS"
    assert decoupling_control["pcb_decoupling"]["status"] == "COMPLETE"
    assert "pcb.decoupling_proximity" not in {
        finding["rule_id"] for finding in decoupling_control["findings"]
    }
    fault_decoupling_coverage = decoupling_fault["pcb_decoupling"]
    control_decoupling_coverage = decoupling_control["pcb_decoupling"]
    assert fault_decoupling_coverage["map_sha256"] == control_decoupling_coverage["map_sha256"]
    assert (
        fault_decoupling_coverage["snapshot_sha256"]
        != control_decoupling_coverage["snapshot_sha256"]
    )

    reference_plane_fault = reports["pcb_reference_plane_fault"]
    assert reference_plane_fault["status"] == "REVIEW"
    assert reference_plane_fault["pcb_reference_plane"]["status"] == "COMPLETE"
    assert "pcb.reference_plane_coverage" in {
        finding["rule_id"] for finding in reference_plane_fault["findings"]
    }
    reference_measurement = reference_plane_fault["pcb_reference_plane"]["entries"][0]["tracks"][0]
    assert reference_measurement["covered_fraction_numerator"] == 4
    assert reference_measurement["covered_fraction_denominator"] == 5
    reference_plane_control = reports["pcb_reference_plane_control"]
    assert reference_plane_control["status"] == "PASS"
    assert reference_plane_control["pcb_reference_plane"]["status"] == "COMPLETE"
    assert reference_plane_control["findings"] == []

    mapped_power_path_fault = reports["mapped_power_path_fault"]
    assert mapped_power_path_fault["status"] == "REVIEW"
    assert "power.mapped_series_path_mismatch" in {
        finding["rule_id"] for finding in mapped_power_path_fault["findings"]
    }
    power_path_run = next(
        run
        for run in mapped_power_path_fault["mapped_check_runs"]
        if run["rule_id"] == "power.mapped_series_path_mismatch"
    )
    assert power_path_run["status"] == "EVALUATED"
    assert power_path_run["requirement_count"] == 1
    assert power_path_run["finding_count"] == 1
    assert reports["mapped_power_path_control"]["status"] == "PASS"
    assert reports["mapped_power_path_control"]["findings"] == []

    power_sequence_fault = reports["mapped_power_sequence_fault"]
    assert power_sequence_fault["status"] == "REVIEW"
    assert "power.mapped_sequence_dependency_mismatch" in {
        finding["rule_id"] for finding in power_sequence_fault["findings"]
    }
    sequence_run = next(
        run
        for run in power_sequence_fault["mapped_check_runs"]
        if run["rule_id"] == "power.mapped_sequence_dependency_mismatch"
    )
    assert sequence_run["status"] == "EVALUATED"
    assert sequence_run["requirement_count"] == 3
    assert sequence_run["finding_count"] == 1
    assert reports["mapped_power_sequence_control"]["status"] == "PASS"
    assert reports["mapped_power_sequence_control"]["findings"] == []

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
