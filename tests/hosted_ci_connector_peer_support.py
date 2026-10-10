"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

import json

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_connector_peer_pin_cases(testcase, results, version):
    peer_pin_fault = results["connector-return-fixture/peer-pin-outlier-fault"]
    peer_pin_control = results["connector-return-fixture/peer-pin-outlier-control"]
    testcase.assertEqual(peer_pin_fault["status"], "PASS")
    testcase.assertEqual(peer_pin_fault["lint_status"], "REVIEW")
    testcase.assertEqual(peer_pin_fault["findings"], "connector.peer_pin_assignment_outlier")
    testcase.assertEqual(peer_pin_fault["subjects"], "Lint:PeerPowerPort pin 1")
    testcase.assertEqual(peer_pin_fault["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
    testcase.assertEqual(peer_pin_control["status"], "PASS")
    testcase.assertEqual(peer_pin_control["lint_status"], "PASS")
    testcase.assertEqual(peer_pin_control["findings"], "none")
    part_id_fault = results["connector-return-fixture/peer-pin-part-id-open-fault"]
    part_id_control = results["connector-return-fixture/peer-pin-part-id-common-control"]
    testcase.assertEqual(part_id_fault["status"], "PASS")
    testcase.assertEqual(part_id_fault["lint_status"], "REVIEW")
    testcase.assertEqual(part_id_fault["findings"], "connector.peer_pin_assignment_outlier")
    testcase.assertEqual(
        part_id_fault["subjects"],
        "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2",
    )
    testcase.assertEqual(part_id_control["status"], "PASS")
    testcase.assertEqual(part_id_control["lint_status"], "PASS")
    testcase.assertEqual(part_id_control["findings"], "none")
    part_id_split = results["connector-return-fixture/peer-pin-part-id-split-fault"]
    testcase.assertEqual(part_id_split["status"], "PASS")
    testcase.assertEqual(part_id_split["lint_status"], "REVIEW")
    testcase.assertEqual(part_id_split["findings"], "connector.peer_pin_assignment_divergence")
    testcase.assertEqual(
        part_id_split["subjects"],
        "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2",
    )
    for (
        case,
        expected_open,
        expected_different,
        expected_common,
        expected_outliers,
        expected_divergences,
    ) in (
        ("peer-pin-part-id-open-fault", 1, 1, 1, 1, 0),
        ("peer-pin-part-id-common-control", 0, 0, 2, 0, 0),
        ("peer-pin-part-id-split-fault", 0, 1, 1, 0, 1),
    ):
        result = results[f"connector-return-fixture/{case}"]
        coverage = json.loads(result["connector_peer_pin_coverage"])
        aliases = coverage["part_id_alias_coverage"]
        testcase.assertEqual(coverage["status"], "NO_EXACT_SYMBOL_PEERS")
        testcase.assertEqual(coverage["netlist_sha256"], result["netlist_sha256"])
        testcase.assertEqual(coverage["connector_candidate_count"], 2)
        testcase.assertEqual(coverage["fitted_connector_count"], 2)
        testcase.assertEqual(coverage["exact_symbol_peer_group_count"], 0)
        testcase.assertEqual(aliases["status"], "EVALUATED")
        testcase.assertEqual(aliases["candidate_group_count"], 1)
        testcase.assertEqual(aliases["eligible_peer_group_count"], 1)
        testcase.assertEqual(aliases["compared_pin_group_count"], 2)
        testcase.assertEqual(aliases["common_assignment_pin_group_count"], expected_common)
        testcase.assertEqual(aliases["different_assignment_pin_group_count"], expected_different)
        testcase.assertEqual(aliases["open_assignment_pin_group_count"], expected_open)
        testcase.assertEqual(aliases["outlier_finding_count"], expected_outliers)
        testcase.assertEqual(aliases["divergence_finding_count"], expected_divergences)
        testcase.assertEqual(result["repeatable"], "true")
    for (
        case,
        expected_connectors,
        expected_outliers,
        expected_common,
        expected_open,
    ) in (
        ("peer-pin-outlier-fault", 3, 1, 1, 1),
        ("peer-pin-outlier-control", 3, 0, 2, 0),
        ("two-peer-open-fault", 2, 1, 1, 1),
        ("two-peer-no-connect-fault", 2, 1, 1, 1),
        ("two-peer-common-control", 2, 0, 2, 0),
    ):
        result = results[f"connector-return-fixture/{case}"]
        coverage = json.loads(result["connector_peer_pin_coverage"])
        testcase.assertEqual(coverage["status"], "EVALUATED")
        testcase.assertEqual(coverage["netlist_sha256"], result["netlist_sha256"])
        testcase.assertEqual(coverage["connector_candidate_count"], expected_connectors)
        testcase.assertEqual(coverage["fitted_connector_count"], expected_connectors)
        testcase.assertEqual(coverage["exact_symbol_peer_group_count"], 1)
        testcase.assertEqual(coverage["exact_symbol_pin_group_count"], 2)
        testcase.assertEqual(coverage["incomplete_pin_inventory_references"], [])
        testcase.assertEqual(coverage["peer_pin_outlier_finding_count"], expected_outliers)
        testcase.assertEqual(
            coverage["exact_symbol_pin_groups_with_common_assignment_count"],
            expected_common,
        )
        testcase.assertEqual(
            coverage["exact_symbol_pin_groups_with_open_assignment_count"],
            expected_open,
        )
    two_peer_fault = results["connector-return-fixture/two-peer-open-fault"]
    two_peer_control = results["connector-return-fixture/two-peer-common-control"]
    testcase.assertEqual(two_peer_fault["status"], "PASS")
    testcase.assertEqual(two_peer_fault["lint_status"], "REVIEW")
    testcase.assertEqual(two_peer_fault["findings"], "connector.peer_pin_assignment_outlier")
    testcase.assertEqual(two_peer_fault["subjects"], "Lint:PeerPowerPort pin 1")
    two_peer_no_connect_fault = results["connector-return-fixture/two-peer-no-connect-fault"]
    testcase.assertEqual(two_peer_no_connect_fault["status"], "PASS")
    testcase.assertEqual(two_peer_no_connect_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        two_peer_no_connect_fault["findings"],
        "connector.peer_pin_assignment_outlier",
    )
    testcase.assertEqual(two_peer_no_connect_fault["subjects"], "Lint:PeerPowerPort pin 1")
    testcase.assertEqual(two_peer_control["status"], "PASS")
    testcase.assertEqual(two_peer_control["lint_status"], "PASS")
    testcase.assertEqual(two_peer_control["findings"], "none")
    offboard_control = results["connector-return-fixture/offboard-interface-control"]
    testcase.assertEqual(offboard_control["status"], "PASS")
    testcase.assertEqual(offboard_control["coverage_status"], "COMPLETE")
    testcase.assertEqual(offboard_control["lint_status"], "PASS")
    testcase.assertEqual(offboard_control["findings"], "none")
    testcase.assertEqual(offboard_control["repeatable"], "true")
    offboard_inventory = results["connector-return-fixture/offboard-inventory-unreviewed"]
    testcase.assertEqual(offboard_inventory["coverage_status"], "UNDECLARED")
    testcase.assertEqual(offboard_inventory["lint_status"], "REVIEW")
    testcase.assertEqual(offboard_inventory["findings"], "none")
    testcase.assertEqual(offboard_inventory["repeatable"], "true")
    peer_pin_minority = results["connector-return-fixture/peer-pin-minority-fault"]
    testcase.assertEqual(peer_pin_minority["status"], "PASS")
    testcase.assertEqual(peer_pin_minority["lint_status"], "REVIEW")
    testcase.assertEqual(peer_pin_minority["findings"], "connector.peer_pin_assignment_outlier")
    testcase.assertEqual(peer_pin_minority["subjects"], "Lint:PeerPowerPort pin 1")
    testcase.assertEqual(peer_pin_minority["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
    peer_pin_divergence = results["connector-return-fixture/peer-pin-divergence-fault"]
    testcase.assertEqual(peer_pin_divergence["status"], "PASS")
    testcase.assertEqual(peer_pin_divergence["lint_status"], "REVIEW")
    testcase.assertEqual(
        peer_pin_divergence["findings"],
        "connector.peer_pin_assignment_divergence",
    )
    testcase.assertEqual(peer_pin_divergence["subjects"], "Lint:PeerPowerPort pin 1")
    testcase.assertEqual(peer_pin_divergence["pin_functions"], "J1.2=GND;J2.2=GND;J3.2=GND")
    placeholder_fault = results["connector-return-fixture/generic-placeholder-divergence-fault"]
    placeholder_control = results["connector-return-fixture/generic-placeholder-control"]
    testcase.assertEqual(placeholder_fault["status"], "PASS")
    testcase.assertEqual(placeholder_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        placeholder_fault["findings"],
        "connector.peer_pin_assignment_divergence",
    )
    testcase.assertEqual(placeholder_fault["subjects"], "Lint:PeerPowerPort pin 1")
    testcase.assertIn("J1.1=Pin_1", placeholder_fault["pin_functions"])
    testcase.assertEqual(placeholder_control["status"], "PASS")
    testcase.assertEqual(placeholder_control["lint_status"], "PASS")
    testcase.assertEqual(placeholder_control["findings"], "none")
    peer_scope_separate = results["connector-return-fixture/peer-scope-separate-fault"]
    peer_scope_shared = results["connector-return-fixture/peer-scope-shared-fault"]
    peer_scope_control = results["connector-return-fixture/peer-scope-shared-control"]
    testcase.assertEqual(peer_scope_separate["status"], "PASS")
    testcase.assertEqual(peer_scope_separate["coverage_status"], "COMPLETE")
    testcase.assertEqual(peer_scope_separate["lint_status"], "REVIEW")
    testcase.assertEqual(peer_scope_separate["findings"], "connector.repeated_pin_function")
    testcase.assertEqual(peer_scope_separate["group_scope"], "separate per-port groups")
    testcase.assertEqual(peer_scope_shared["status"], "PASS")
    testcase.assertEqual(peer_scope_shared["coverage_status"], "COMPLETE")
    testcase.assertEqual(peer_scope_shared["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(peer_scope_shared["findings"].split(",")),
        {
            "connector.repeated_pin_function",
            "connector.peer_pin_assignment_divergence",
        },
    )
    testcase.assertEqual(peer_scope_shared["group_scope"], "shared uart-peer-set")
    testcase.assertEqual(peer_scope_control["status"], "PASS")
    testcase.assertEqual(peer_scope_control["coverage_status"], "COMPLETE")
    testcase.assertEqual(peer_scope_control["lint_status"], "PASS")
    testcase.assertEqual(peer_scope_control["findings"], "none")
    assert_connector_result_sources(
        testcase,
        results,
        version,
        (
            "peer-power-fault",
            "peer-power-control",
            "peer-pin-outlier-fault",
            "peer-pin-outlier-control",
            "peer-pin-part-id-open-fault",
            "peer-pin-part-id-common-control",
            "peer-pin-part-id-split-fault",
            "two-peer-open-fault",
            "two-peer-no-connect-fault",
            "two-peer-common-control",
            "single-offboard-port-control",
            "offboard-inventory-unreviewed",
            "offboard-interface-control",
            "peer-pin-minority-fault",
            "peer-pin-divergence-fault",
            "generic-placeholder-divergence-fault",
            "generic-placeholder-control",
            "peer-scope-split-return-fault",
            "peer-scope-separate-fault",
            "peer-scope-shared-fault",
            "peer-scope-shared-control",
        ),
    )
