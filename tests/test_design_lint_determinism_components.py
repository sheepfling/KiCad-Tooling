"""Components hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
]


def test_two_pin_component_reports_remain_deterministic() -> None:
    reports = hashseed_probe_reports(families=("components",))
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
    for report_name in ("led_output_direct_fault", "led_output_parallel_resistor_fault"):
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
