"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

from tests.hosted_ci_connector_common_support import assert_connector_result_sources


def assert_connector_power_and_role_cases(testcase, results, version):
    generic_power_fault = results["connector-return-fixture/unconnected-generic-power-input-fault"]
    generic_power_control = results[
        "connector-return-fixture/unconnected-generic-power-input-control"
    ]
    testcase.assertEqual(generic_power_fault["status"], "PASS")
    testcase.assertEqual(generic_power_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        generic_power_fault["findings"].split(","),
        ["connector.unconnected_power_input"] * 2,
    )
    testcase.assertEqual(
        set(generic_power_fault["subjects"].split(";")),
        {
            "J1.1: generic native power-input pin is unassigned",
            "J2.1: generic native power-input pin is unassigned",
        },
    )
    testcase.assertEqual(
        generic_power_fault["pin_electrical_types"],
        "J1.1=power_in;J1.2=passive;J2.1=power_in;J2.2=passive",
    )
    testcase.assertEqual(generic_power_control["status"], "PASS")
    testcase.assertEqual(generic_power_control["lint_status"], "PASS")
    testcase.assertEqual(generic_power_control["findings"], "none")
    testcase.assertEqual(
        generic_power_control["pin_electrical_types"],
        generic_power_fault["pin_electrical_types"],
    )
    for case in (
        "unconnected-generic-component-power-input-fault",
        "unconnected-generic-component-power-input-no-connect-fault",
    ):
        item = results[f"connector-return-fixture/{case}"]
        testcase.assertEqual(item["status"], "PASS")
        testcase.assertEqual(item["lint_status"], "REVIEW")
        testcase.assertEqual(item["findings"], "component.unconnected_power_input")
    for case in (
        "unconnected-generic-component-power-input-control",
        "unconnected-generic-component-power-input-dnp-control",
    ):
        item = results[f"connector-return-fixture/{case}"]
        testcase.assertEqual(item["status"], "PASS")
        testcase.assertEqual(item["lint_status"], "PASS")
        testcase.assertEqual(item["findings"], "none")

    channel_fault = results["connector-return-fixture/channel-power-fault"]
    channel_control = results["connector-return-fixture/channel-power-control"]
    testcase.assertEqual(channel_fault["status"], "PASS")
    testcase.assertEqual(channel_fault["lint_status"], "REVIEW")
    testcase.assertIn("net.numbered_power_rails", channel_fault["findings"].split(","))
    testcase.assertIn("CH VDD", channel_fault["subjects"].split(";"))
    testcase.assertEqual(channel_control["status"], "PASS")
    testcase.assertEqual(channel_control["lint_status"], "PASS")
    testcase.assertEqual(channel_control["findings"], "none")
    testcase.assertIn("J1.3=VDD", channel_fault["pin_functions"])
    peer_power_fault = results["connector-return-fixture/peer-power-fault"]
    peer_power_control = results["connector-return-fixture/peer-power-control"]
    testcase.assertEqual(peer_power_fault["status"], "PASS")
    testcase.assertEqual(peer_power_fault["lint_status"], "REVIEW")
    testcase.assertEqual(
        set(peer_power_fault["findings"].split(",")),
        {"connector.repeated_pin_function", "net.numbered_power_rails"},
    )
    testcase.assertIn("J3.1=1", peer_power_fault["pin_functions"])
    testcase.assertEqual(peer_power_control["status"], "PASS")
    testcase.assertEqual(peer_power_control["lint_status"], "PASS")
    testcase.assertEqual(peer_power_control["findings"], "none")

    mapped_role_fault = results["connector-return-fixture/reviewed-role-fault"]
    mapped_role_control = results["connector-return-fixture/reviewed-role-control"]
    testcase.assertEqual(mapped_role_fault["status"], "PASS")
    testcase.assertEqual(mapped_role_fault["coverage_status"], "COMPLETE")
    testcase.assertEqual(mapped_role_fault["lint_status"], "REVIEW")
    testcase.assertEqual(mapped_role_fault["findings"], "connector.repeated_pin_function")
    testcase.assertEqual(mapped_role_fault["repeatable"], "true")
    testcase.assertEqual(mapped_role_control["status"], "PASS")
    testcase.assertEqual(mapped_role_control["coverage_status"], "COMPLETE")
    testcase.assertEqual(mapped_role_control["lint_status"], "PASS")
    testcase.assertEqual(mapped_role_control["findings"], "none")
    testcase.assertEqual(mapped_role_control["repeatable"], "true")
    mapped_supply_fault = results["connector-return-fixture/reviewed-supply-fault"]
    mapped_supply_control = results["connector-return-fixture/reviewed-supply-control"]
    mapped_supply_domain_control = results[
        "connector-return-fixture/reviewed-supply-domain-control"
    ]
    testcase.assertEqual(mapped_supply_fault["status"], "PASS")
    testcase.assertEqual(mapped_supply_fault["coverage_status"], "COMPLETE")
    testcase.assertEqual(mapped_supply_fault["lint_status"], "REVIEW")
    testcase.assertEqual(mapped_supply_fault["findings"], "connector.repeated_pin_function")
    testcase.assertEqual(mapped_supply_fault["repeatable"], "true")
    testcase.assertEqual(mapped_supply_control["coverage_status"], "COMPLETE")
    testcase.assertEqual(mapped_supply_control["lint_status"], "PASS")
    testcase.assertEqual(mapped_supply_control["findings"], "none")
    testcase.assertEqual(mapped_supply_control["repeatable"], "true")
    testcase.assertEqual(mapped_supply_domain_control["coverage_status"], "COMPLETE")
    testcase.assertEqual(mapped_supply_domain_control["lint_status"], "PASS")
    testcase.assertEqual(mapped_supply_domain_control["findings"], "none")
    testcase.assertEqual(mapped_supply_domain_control["repeatable"], "true")
    assert_connector_result_sources(
        testcase,
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
