"""Components hash-seed report regressions."""

from __future__ import annotations

import pytest

from tests.design_lint_fixtures.hashseed_reports import hashseed_probe_reports

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.slow,
    pytest.mark.component_lint,
    pytest.mark.power_lint,
    pytest.mark.return_path_lint,
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


@pytest.mark.design_lint_rule(rule_id="component.diode_anode_below_cathode_on_named_rails")
def test_named_return_diode_fault_and_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["diode_rail_named_return_fault"]
    control = reports["diode_rail_named_return_control"]
    rule_id = "component.diode_anode_below_cathode_on_named_rails"

    fault_findings = [finding for finding in fault["findings"] if finding["rule_id"] == rule_id]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["anode_net"] == ["GND"]
    assert fault_findings[0]["evidence"]["cathode_net"] == ["+3V3"]
    assert control["status"] == "PASS"
    assert control["findings"] == []


@pytest.mark.design_lint_rule(rule_id="component.mosfet_gate_without_peer")
@pytest.mark.design_lint_rule(rule_id="component.mosfet_gate_without_visible_source_bias")
def test_mosfet_gate_fault_and_driver_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["mosfet_gate_no_peer_fault"]
    control = reports["mosfet_gate_driver_control"]
    rule_id = "component.mosfet_gate_without_peer"
    source_bias_rule_id = "component.mosfet_gate_without_visible_source_bias"

    fault_findings = [finding for finding in fault["findings"] if finding["rule_id"] == rule_id]
    control_source_bias_findings = [
        finding for finding in control["findings"] if finding["rule_id"] == source_bias_rule_id
    ]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["gate_pin"] == ["Q1.2"]
    assert fault_findings[0]["evidence"]["other_fitted_net_members"] == []
    assert control["status"] == "PASS"
    assert all(finding["rule_id"] != rule_id for finding in control["findings"])
    assert fault["netlist_sha256"] != control["netlist_sha256"]
    assert len(control_source_bias_findings) == 1
    assert control_source_bias_findings[0]["mode"] == "off"
    assert control_source_bias_findings[0]["disposition"] == "RULE_OFF"


@pytest.mark.design_lint_rule(rule_id="component.mosfet_terminal_order_on_named_rails")
def test_mosfet_rail_order_fault_and_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["mosfet_terminal_order_fault"]
    control = reports["mosfet_terminal_order_control"]
    rule_id = "component.mosfet_terminal_order_on_named_rails"

    fault_findings = [finding for finding in fault["findings"] if finding["rule_id"] == rule_id]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["drain_net"] == ["GND"]
    assert fault_findings[0]["evidence"]["source_net"] == ["+5V"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != rule_id for item in control["findings"])
    assert all(item["disposition"] == "RULE_OFF" for item in control["findings"])


@pytest.mark.design_lint_rule(rule_id="component.bjt_terminal_order_on_named_rails")
def test_bjt_rail_order_fault_and_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    rule_id = "component.bjt_terminal_order_on_named_rails"

    for family in ("npn", "pnp"):
        fault = reports[f"bjt_{family}_terminal_order_fault"]
        control = reports[f"bjt_{family}_terminal_order_control"]
        fault_findings = [item for item in fault["findings"] if item["rule_id"] == rule_id]
        assert fault["status"] == "REVIEW"
        assert len(fault_findings) == 1
        assert fault_findings[0]["evidence"]["transistor_family"] == [family]
        assert control["status"] == "PASS"
        assert all(item["rule_id"] != rule_id for item in control["findings"])


@pytest.mark.design_lint_rule(rule_id="component.bjt_collector_emitter_same_net")
def test_bjt_same_net_fault_and_distinct_net_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["bjt_collector_emitter_same_net_fault"]
    control = reports["bjt_collector_emitter_same_net_control"]
    rule_id = "component.bjt_collector_emitter_same_net"

    fault_findings = [item for item in fault["findings"] if item["rule_id"] == rule_id]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["collector_net"] == ["CE_SHARED"]
    assert fault_findings[0]["evidence"]["emitter_net"] == ["CE_SHARED"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != rule_id for item in control["findings"])


@pytest.mark.design_lint_rule(rule_id="component.bjt_base_emitter_same_net")
def test_bjt_base_emitter_same_net_fault_and_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["bjt_base_emitter_same_net_fault"]
    control = reports["bjt_base_emitter_same_net_control"]
    rule_id = "component.bjt_base_emitter_same_net"

    fault_findings = [item for item in fault["findings"] if item["rule_id"] == rule_id]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["base_net"] == ["BE_SHARED"]
    assert fault_findings[0]["evidence"]["emitter_net"] == ["BE_SHARED"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != rule_id for item in control["findings"])


@pytest.mark.design_lint_rule(rule_id="component.bjt_base_direct_drive")
def test_bjt_base_direct_drive_fault_and_series_control_are_stable_across_hash_seeds() -> None:
    reports = hashseed_probe_reports(families=("components",))
    fault = reports["bjt_base_direct_drive_fault"]
    control = reports["bjt_base_series_resistor_control"]
    rule_id = "component.bjt_base_direct_drive"

    fault_findings = [item for item in fault["findings"] if item["rule_id"] == rule_id]
    assert fault["status"] == "REVIEW"
    assert len(fault_findings) == 1
    assert fault_findings[0]["evidence"]["base_pin"] == ["Q1.1"]
    assert fault_findings[0]["evidence"]["output_pins"] == ["U1.1"]
    assert control["status"] == "PASS"
    assert all(item["rule_id"] != rule_id for item in control["findings"])
