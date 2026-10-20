"""Theme-owned assertions for unconnected component power-input findings."""

from __future__ import annotations

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_unconnected_component_power_input_cases(results, version):
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    ):
        item = results[f"connector-return-fixture/{case}"]
        assert item["status"] == "PASS"
        assert item["lint_status"] == "REVIEW"
        assert item["findings"] == "component.unconnected_power_input"
        assert item["subjects"] == "U1.1: generic native power-input pin is unassigned"
        assert item["pin_electrical_types"] == "U1.1=power_in;U1.2=passive"

    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        item = results[f"connector-return-fixture/{case}"]
        assert item["status"] == "PASS"
        assert item["lint_status"] == "PASS"
        assert item["findings"] == "none"
        assert item["pin_electrical_types"] == "U1.1=power_in;U1.2=passive"

    assert_connector_result_sources(
        results,
        version,
        (
            "unconnected-generic-component-power-input-fault",
            "unconnected-generic-component-power-input-control",
            "unconnected-generic-component-power-input-no-connect-fault",
            "unconnected-generic-component-power-input-dnp-control",
        ),
    )
