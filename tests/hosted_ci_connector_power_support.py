"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_connector_power_and_role_cases(results, version):
    generic_power_fault = results["connector-return-fixture/unconnected-generic-power-input-fault"]
    generic_power_control = results[
        "connector-return-fixture/unconnected-generic-power-input-control"
    ]
    assert generic_power_fault["status"] == "PASS"
    assert generic_power_fault["lint_status"] == "REVIEW"
    assert generic_power_fault["findings"].split(",") == ["connector.unconnected_power_input"] * 2
    assert set(generic_power_fault["subjects"].split(";")) == {
        "J1.1: generic native power-input pin is unassigned",
        "J2.1: generic native power-input pin is unassigned",
    }
    assert (
        generic_power_fault["pin_electrical_types"]
        == "J1.1=power_in;J1.2=passive;J2.1=power_in;J2.2=passive"
    )
    assert generic_power_control["status"] == "PASS"
    assert generic_power_control["lint_status"] == "PASS"
    assert generic_power_control["findings"] == "none"
    assert (
        generic_power_control["pin_electrical_types"] == generic_power_fault["pin_electrical_types"]
    )
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    ):
        item = results[f"connector-return-fixture/{case}"]
        assert item["status"] == "PASS"
        assert item["lint_status"] == "REVIEW"
        assert item["findings"] == "component.unconnected_power_input"
    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        item = results[f"connector-return-fixture/{case}"]
        assert item["status"] == "PASS"
        assert item["lint_status"] == "PASS"
        assert item["findings"] == "none"

    channel_fault = results["connector-return-fixture/channel-power-fault"]
    channel_control = results["connector-return-fixture/channel-power-control"]
    assert channel_fault["status"] == "PASS"
    assert channel_fault["lint_status"] == "REVIEW"
    assert "net.numbered_power_rails" in channel_fault["findings"].split(",")
    assert "CH VDD" in channel_fault["subjects"].split(";")
    assert channel_control["status"] == "PASS"
    assert channel_control["lint_status"] == "PASS"
    assert channel_control["findings"] == "none"
    assert "J1.3=VDD" in channel_fault["pin_functions"]
    peer_power_fault = results["connector-return-fixture/peer-power-fault"]
    peer_power_control = results["connector-return-fixture/peer-power-control"]
    assert peer_power_fault["status"] == "PASS"
    assert peer_power_fault["lint_status"] == "REVIEW"
    assert set(peer_power_fault["findings"].split(",")) == {
        "connector.repeated_pin_function",
        "net.numbered_power_rails",
    }
    assert "J3.1=1" in peer_power_fault["pin_functions"]
    assert peer_power_control["status"] == "PASS"
    assert peer_power_control["lint_status"] == "PASS"
    assert peer_power_control["findings"] == "none"

    mapped_role_fault = results["connector-return-fixture/reviewed-role-fault"]
    mapped_role_control = results["connector-return-fixture/reviewed-role-control"]
    assert mapped_role_fault["status"] == "PASS"
    assert mapped_role_fault["coverage_status"] == "COMPLETE"
    assert mapped_role_fault["lint_status"] == "REVIEW"
    assert mapped_role_fault["findings"] == "connector.repeated_pin_function"
    assert mapped_role_fault["repeatable"] == "true"
    assert mapped_role_control["status"] == "PASS"
    assert mapped_role_control["coverage_status"] == "COMPLETE"
    assert mapped_role_control["lint_status"] == "PASS"
    assert mapped_role_control["findings"] == "none"
    assert mapped_role_control["repeatable"] == "true"
    mapped_supply_fault = results["connector-return-fixture/reviewed-supply-fault"]
    mapped_supply_control = results["connector-return-fixture/reviewed-supply-control"]
    mapped_supply_domain_control = results[
        "connector-return-fixture/reviewed-supply-domain-control"
    ]
    assert mapped_supply_fault["status"] == "PASS"
    assert mapped_supply_fault["coverage_status"] == "COMPLETE"
    assert mapped_supply_fault["lint_status"] == "REVIEW"
    assert mapped_supply_fault["findings"] == "connector.repeated_pin_function"
    assert mapped_supply_fault["repeatable"] == "true"
    assert mapped_supply_control["coverage_status"] == "COMPLETE"
    assert mapped_supply_control["lint_status"] == "PASS"
    assert mapped_supply_control["findings"] == "none"
    assert mapped_supply_control["repeatable"] == "true"
    assert mapped_supply_domain_control["coverage_status"] == "COMPLETE"
    assert mapped_supply_domain_control["lint_status"] == "PASS"
    assert mapped_supply_domain_control["findings"] == "none"
    assert mapped_supply_domain_control["repeatable"] == "true"
    assert_connector_result_sources(
        results,
        version,
        (
            "channel-power-fault",
            "channel-power-control",
            "mapped-supply-fault",
            "mapped-supply-control",
            "reviewed-role-fault",
            "reviewed-role-control",
            "reviewed-supply-fault",
            "reviewed-supply-control",
            "reviewed-supply-domain-control",
            "unconnected-generic-power-input-fault",
            "unconnected-generic-power-input-control",
        ),
    )
