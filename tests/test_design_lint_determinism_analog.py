"""Hash-seed regressions for mapped analog design-lint reports."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [pytest.mark.design_lint, pytest.mark.slow, pytest.mark.component_lint]


@pytest.mark.parametrize(
    (
        "family",
        "fault_key",
        "control_key",
        "coverage_key",
        "rule_id",
        "fault_coverage",
        "fault_entry_status",
    ),
    (
        (
            "crystal network",
            "mapped_crystal_network_fault",
            "mapped_crystal_network_control",
            "crystal_network_coverage",
            "oscillator.crystal_load_network_mismatch",
            "INCOMPLETE",
            "INCOMPLETE",
        ),
        (
            "RC filter",
            "mapped_rc_filter_fault",
            "mapped_rc_filter_control",
            "rc_filter_coverage",
            "filter.rc_corner_mismatch",
            "COMPLETE",
            "OUT_OF_RANGE",
        ),
    ),
)
def test_mapped_analog_reports_remain_source_bound_and_deterministic(
    family: str,
    fault_key: str,
    control_key: str,
    coverage_key: str,
    rule_id: str,
    fault_coverage: str,
    fault_entry_status: str,
) -> None:
    reports = hashseed_probe_reports(families=("analog",))
    fault_case = reports[fault_key]
    control_case = reports[control_key]

    assert fault_case["requirement_sha256"] == control_case["requirement_sha256"], family
    assert fault_case["netlist_sha256"] != control_case["netlist_sha256"]

    fault = fault_case["report"]
    control = control_case["report"]
    assert fault["status"] == "REVIEW"
    assert fault["netlist_sha256"] == fault_case["netlist_sha256"]
    assert fault[coverage_key]["status"] == fault_coverage
    assert fault[coverage_key]["entries"][0]["status"] == fault_entry_status
    assert rule_id in {finding["rule_id"] for finding in fault["findings"]}, family

    assert control["status"] == "PASS"
    assert control["netlist_sha256"] == control_case["netlist_sha256"]
    assert control[coverage_key]["status"] == "COMPLETE"
    assert control["findings"] == [], family
