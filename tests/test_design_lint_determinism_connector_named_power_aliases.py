"""Cross-process determinism for named connector power-alias rules."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]


def test_named_power_alias_faults_and_controls_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("connector_named_power_aliases",))
    for direction, rule_id in (
        ("input", "connector.peer_power_input_named_assignment_divergence"),
        ("output", "connector.peer_power_output_named_assignment_divergence"),
    ):
        fault = reports[f"named_connector_power_{direction}_divergence_fault"]
        control = reports[f"named_connector_power_{direction}_common_control"]
        fault_rule_ids = {finding["rule_id"] for finding in fault["findings"]}
        control_rule_ids = {finding["rule_id"] for finding in control["findings"]}

        assert fault["status"] == "REVIEW"
        assert fault["netlist_sha256"] != control["netlist_sha256"]
        assert rule_id in fault_rule_ids
        assert rule_id not in control_rule_ids
        finding = next(item for item in fault["findings"] if item["rule_id"] == rule_id)
        assert finding["evidence"]["distinct_net_assignments"] == [
            "J1.1=SYNTHETIC_RAIL_A",
            "J2.1=SYNTHETIC_RAIL_B",
        ]
