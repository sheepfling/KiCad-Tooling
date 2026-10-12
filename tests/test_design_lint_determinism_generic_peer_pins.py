"""Cross-process determinism for generic component peer-pin heuristics."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.component_lint,
]


def _rule_ids(report: dict[str, object]) -> set[str]:
    return {finding["rule_id"] for finding in report["findings"]}


def _assert_fault_control_reports(
    reports: dict[str, object], fault_name: str, control_name: str, rule_id: str
) -> None:
    fault = reports[fault_name]
    control = reports[control_name]
    assert fault["status"] == "REVIEW"
    assert control["status"] == "PASS"
    assert fault["netlist_sha256"] != control["netlist_sha256"]
    assert _rule_ids(fault) == {rule_id}
    assert rule_id not in _rule_ids(control)

    for report, expected_count in ((fault, 1), (control, 0)):
        coverage = next(
            item for item in report["component_peer_pin_coverage"] if item["rule_id"] == rule_id
        )
        assert coverage["status"] == "EVALUATED"
        assert coverage["netlist_sha256"] == report["netlist_sha256"]
        assert coverage["candidate_group_count"] == expected_count
        assert coverage["finding_count"] == expected_count
        assert coverage["suppressed_candidate_count"] == 0


def test_generic_peer_pin_all_open_reports_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("component_peers",))
    _assert_fault_control_reports(
        reports,
        "generic_peer_pin_all_open_fault",
        "generic_peer_pin_all_open_control",
        "component.generic_peer_pin_all_open",
    )


def test_generic_peer_pin_mixed_open_reports_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("component_peers",))
    _assert_fault_control_reports(
        reports,
        "generic_peer_pin_mixed_open_fault",
        "generic_peer_pin_mixed_open_control",
        "component.generic_peer_pin_mixed_open",
    )


def test_generic_peer_pin_assignment_outlier_reports_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("component_peers",))
    _assert_fault_control_reports(
        reports,
        "generic_peer_pin_assignment_outlier_fault",
        "generic_peer_pin_assignment_outlier_control",
        "component.generic_peer_pin_assignment_outlier",
    )
