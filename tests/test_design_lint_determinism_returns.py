"""Returns hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.return_path_lint,
    pytest.mark.connector_lint,
]


def test_return_and_ground_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("returns",))
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
