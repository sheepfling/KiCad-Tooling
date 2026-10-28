"""Cross-process determinism for component peer power-input heuristics."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports
from tests.json_types import JsonObject

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


def _rule_ids(report: JsonObject) -> set[str]:
    return {finding["rule_id"] for finding in report["findings"]}


def _coverage(report: JsonObject, rule_id: str) -> JsonObject:
    return next(
        item for item in report["component_peer_pin_coverage"] if item["rule_id"] == rule_id
    )


def test_power_input_peer_fault_controls_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("component_peers",))
    scenarios = (
        (
            "peer_power_input_assignment_fault",
            "peer_power_input_assignment_control",
            "component.peer_power_input_assignment_divergence",
        ),
        (
            "named_peer_power_input_partial_open_fault",
            "named_peer_power_input_partial_open_control",
            "component.peer_power_input_open_assignment",
        ),
        (
            "named_peer_power_input_divergence_fault",
            "named_peer_power_input_divergence_control",
            "component.peer_power_input_named_assignment_divergence",
        ),
        (
            "named_peer_power_input_all_open_fault",
            "named_peer_power_input_all_open_control",
            "component.peer_power_input_named_all_open",
        ),
    )

    for fault_name, control_name, rule_id in scenarios:
        fault = reports[fault_name]
        control = reports[control_name]
        assert fault["status"] == "REVIEW"
        assert fault["netlist_sha256"] != control["netlist_sha256"]
        assert _rule_ids(fault) == {rule_id}
        assert rule_id not in _rule_ids(control)
        for report, candidate_count in ((fault, 1), (control, 0)):
            coverage = _coverage(report, rule_id)
            assert coverage["status"] == "EVALUATED"
            assert coverage["netlist_sha256"] == report["netlist_sha256"]
            assert coverage["candidate_group_count"] == candidate_count
            assert coverage["finding_count"] == candidate_count
