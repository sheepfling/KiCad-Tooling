"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

import json

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_connector_peer_pin_cases(results, version):
    peer_pin_fault = results["connector-return-fixture/peer-pin-outlier-fault"]
    peer_pin_control = results["connector-return-fixture/peer-pin-outlier-control"]
    assert peer_pin_fault["status"] == "PASS"
    assert peer_pin_fault["lint_status"] == "REVIEW"
    assert peer_pin_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert peer_pin_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    assert peer_pin_fault["pin_functions"] == "J1.2=GND;J2.2=GND;J3.2=GND"
    assert peer_pin_control["status"] == "PASS"
    assert peer_pin_control["lint_status"] == "PASS"
    assert peer_pin_control["findings"] == "none"
    part_id_fault = results["connector-return-fixture/peer-pin-part-id-open-fault"]
    part_id_control = results["connector-return-fixture/peer-pin-part-id-common-control"]
    assert part_id_fault["status"] == "PASS"
    assert part_id_fault["lint_status"] == "REVIEW"
    assert part_id_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert part_id_fault["subjects"] == "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
    assert part_id_control["status"] == "PASS"
    assert part_id_control["lint_status"] == "PASS"
    assert part_id_control["findings"] == "none"
    part_id_split = results["connector-return-fixture/peer-pin-part-id-split-fault"]
    assert part_id_split["status"] == "PASS"
    assert part_id_split["lint_status"] == "REVIEW"
    assert part_id_split["findings"] == "connector.peer_pin_assignment_divergence"
    assert part_id_split["subjects"] == "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2"
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
        assert coverage["status"] == "NO_EXACT_SYMBOL_PEERS"
        assert coverage["netlist_sha256"] == result["netlist_sha256"]
        assert coverage["connector_candidate_count"] == 2
        assert coverage["fitted_connector_count"] == 2
        assert coverage["exact_symbol_peer_group_count"] == 0
        assert aliases["status"] == "EVALUATED"
        assert aliases["candidate_group_count"] == 1
        assert aliases["eligible_peer_group_count"] == 1
        assert aliases["compared_pin_group_count"] == 2
        assert aliases["common_assignment_pin_group_count"] == expected_common
        assert aliases["different_assignment_pin_group_count"] == expected_different
        assert aliases["open_assignment_pin_group_count"] == expected_open
        assert aliases["outlier_finding_count"] == expected_outliers
        assert aliases["divergence_finding_count"] == expected_divergences
        assert result["repeatable"] == "true"
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
        assert coverage["status"] == "EVALUATED"
        assert coverage["netlist_sha256"] == result["netlist_sha256"]
        assert coverage["connector_candidate_count"] == expected_connectors
        assert coverage["fitted_connector_count"] == expected_connectors
        assert coverage["exact_symbol_peer_group_count"] == 1
        assert coverage["exact_symbol_pin_group_count"] == 2
        assert coverage["incomplete_pin_inventory_references"] == []
        assert coverage["peer_pin_outlier_finding_count"] == expected_outliers
        assert coverage["exact_symbol_pin_groups_with_common_assignment_count"] == expected_common
        assert coverage["exact_symbol_pin_groups_with_open_assignment_count"] == expected_open
    two_peer_fault = results["connector-return-fixture/two-peer-open-fault"]
    two_peer_control = results["connector-return-fixture/two-peer-common-control"]
    assert two_peer_fault["status"] == "PASS"
    assert two_peer_fault["lint_status"] == "REVIEW"
    assert two_peer_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert two_peer_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    two_peer_no_connect_fault = results["connector-return-fixture/two-peer-no-connect-fault"]
    assert two_peer_no_connect_fault["status"] == "PASS"
    assert two_peer_no_connect_fault["lint_status"] == "REVIEW"
    assert two_peer_no_connect_fault["findings"] == "connector.peer_pin_assignment_outlier"
    assert two_peer_no_connect_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    assert two_peer_control["status"] == "PASS"
    assert two_peer_control["lint_status"] == "PASS"
    assert two_peer_control["findings"] == "none"
    all_open_fault = results["connector-return-fixture/all-open-generic-peer-fault"]
    all_open_control = results["connector-return-fixture/all-open-generic-peer-control"]
    assert all_open_fault["status"] == "PASS"
    assert all_open_fault["lint_status"] == "REVIEW"
    assert all_open_fault["findings"] == "connector.generic_peer_pin_all_open"
    assert all_open_fault["subjects"] == (
        "Lint:PeerPowerPort pin 2: generic passive contact is open on every peer"
    )
    assert all_open_fault["pin_functions"] == "J1.2=Pin_2;J2.2=Pin_2"
    assert all_open_control["status"] == "PASS"
    assert all_open_control["lint_status"] == "PASS"
    assert all_open_control["findings"] == "none"
    part_id_all_open = results["connector-return-fixture/part-id-all-open-generic-peer-fault"]
    part_id_control = results["connector-return-fixture/peer-pin-part-id-common-control"]
    assert part_id_all_open["status"] == "PASS"
    assert part_id_all_open["lint_status"] == "REVIEW"
    assert part_id_all_open["findings"] == "connector.generic_peer_pin_all_open"
    assert part_id_all_open["subjects"] == (
        "PART_ID SYNTHETIC-CONNECTOR-2PIN-001 pin 2: generic passive contact is open on every peer"
    )
    part_id_coverage = json.loads(part_id_all_open["connector_peer_pin_coverage"])
    assert part_id_coverage["generic_peer_pin_all_open_finding_count"] == 1
    assert part_id_coverage["part_id_alias_coverage"]["eligible_peer_group_count"] == 1
    assert part_id_control["lint_status"] == "PASS"
    assert part_id_control["findings"] == "none"
    offboard_control = results["connector-return-fixture/offboard-interface-control"]
    assert offboard_control["status"] == "PASS"
    assert offboard_control["coverage_status"] == "COMPLETE"
    assert offboard_control["lint_status"] == "PASS"
    assert offboard_control["findings"] == "none"
    assert offboard_control["repeatable"] == "true"
    offboard_inventory = results["connector-return-fixture/offboard-inventory-unreviewed"]
    assert offboard_inventory["coverage_status"] == "UNDECLARED"
    assert offboard_inventory["lint_status"] == "REVIEW"
    assert offboard_inventory["findings"] == "none"
    assert offboard_inventory["repeatable"] == "true"
    peer_pin_minority = results["connector-return-fixture/peer-pin-minority-fault"]
    assert peer_pin_minority["status"] == "PASS"
    assert peer_pin_minority["lint_status"] == "REVIEW"
    assert peer_pin_minority["findings"] == "connector.peer_pin_assignment_outlier"
    assert peer_pin_minority["subjects"] == "Lint:PeerPowerPort pin 1"
    assert peer_pin_minority["pin_functions"] == "J1.2=GND;J2.2=GND;J3.2=GND"
    peer_pin_divergence = results["connector-return-fixture/peer-pin-divergence-fault"]
    assert peer_pin_divergence["status"] == "PASS"
    assert peer_pin_divergence["lint_status"] == "REVIEW"
    assert peer_pin_divergence["findings"] == "connector.peer_pin_assignment_divergence"
    assert peer_pin_divergence["subjects"] == "Lint:PeerPowerPort pin 1"
    assert peer_pin_divergence["pin_functions"] == "J1.2=GND;J2.2=GND;J3.2=GND"
    placeholder_fault = results["connector-return-fixture/generic-placeholder-divergence-fault"]
    placeholder_control = results["connector-return-fixture/generic-placeholder-control"]
    assert placeholder_fault["status"] == "PASS"
    assert placeholder_fault["lint_status"] == "REVIEW"
    assert placeholder_fault["findings"] == "connector.peer_pin_assignment_divergence"
    assert placeholder_fault["subjects"] == "Lint:PeerPowerPort pin 1"
    assert "J1.1=Pin_1" in placeholder_fault["pin_functions"]
    assert placeholder_control["status"] == "PASS"
    assert placeholder_control["lint_status"] == "PASS"
    assert placeholder_control["findings"] == "none"
    peer_scope_separate = results["connector-return-fixture/peer-scope-separate-fault"]
    peer_scope_shared = results["connector-return-fixture/peer-scope-shared-fault"]
    peer_scope_control = results["connector-return-fixture/peer-scope-shared-control"]
    assert peer_scope_separate["status"] == "PASS"
    assert peer_scope_separate["coverage_status"] == "COMPLETE"
    assert peer_scope_separate["lint_status"] == "REVIEW"
    assert peer_scope_separate["findings"] == "connector.repeated_pin_function"
    assert peer_scope_separate["group_scope"] == "separate per-port groups"
    assert peer_scope_shared["status"] == "PASS"
    assert peer_scope_shared["coverage_status"] == "COMPLETE"
    assert peer_scope_shared["lint_status"] == "REVIEW"
    assert set(peer_scope_shared["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "connector.peer_pin_assignment_divergence",
    }
    assert peer_scope_shared["group_scope"] == "shared uart-peer-set"
    assert peer_scope_control["status"] == "PASS"
    assert peer_scope_control["coverage_status"] == "COMPLETE"
    assert peer_scope_control["lint_status"] == "PASS"
    assert peer_scope_control["findings"] == "none"
    assert_connector_result_sources(
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
            "all-open-generic-peer-fault",
            "all-open-generic-peer-control",
            "all-open-generic-signal-peer-fault",
            "all-open-generic-signal-peer-control",
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
