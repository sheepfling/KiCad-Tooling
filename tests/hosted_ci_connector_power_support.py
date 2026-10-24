"""Theme-owned assertions for synthetic connector native fixtures."""

from __future__ import annotations

import json

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
    mapped_supply_scope_review = results["connector-return-fixture/reviewed-supply-scope-review"]
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
    assert mapped_supply_scope_review["coverage_status"] == "COMPLETE"
    assert mapped_supply_scope_review["lint_status"] == "REVIEW"
    assert mapped_supply_scope_review["findings"] == "connector.return_supply_scope_singleton"
    assert mapped_supply_scope_review["comparison_scope"] == "distinct reviewed supply groups"
    assert mapped_supply_scope_review["repeatable"] == "true"
    scope_evidence = json.loads(mapped_supply_scope_review["evidence"])
    assert scope_evidence["comparison_role"] == ["supply in voltage domain external-5v"]
    assert scope_evidence["comparable_references"] == ["J1", "J2"]
    assert scope_evidence["isolated_references"] == ["J1", "J2"]
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
            "reviewed-supply-scope-review",
            "unconnected-generic-power-input-fault",
            "unconnected-generic-power-input-control",
        ),
    )


def assert_mapped_supply_domain_sharing_fault(results, version):
    fault = results["connector-return-fixture/reviewed-supply-domain-sharing-fault"]
    assert fault["status"] == "PASS"
    assert fault["coverage_status"] == "COMPLETE"
    assert fault["lint_status"] == "REVIEW"
    assert fault["findings"] == "connector.mapped_supply_domains_share_net"
    assert fault["subjects"] == (
        "COMMON_SUPPLY: mapped connector supply domains share one native net"
    )
    assert fault["repeatable"] == "true"
    evidence = json.loads(fault["evidence"])
    assert evidence["native_shared_net"] == ["COMMON_SUPPLY"]
    assert evidence["reviewed_voltage_domains"] == ["external-5v", "isolated-5v"]
    assert evidence["mapped_supply_assignments"] == [
        "J1.1=COMMON_SUPPLY; voltage_domain=external-5v",
        "J2.9=COMMON_SUPPLY; voltage_domain=isolated-5v",
    ]
    assert evidence["J1.1"] == evidence["J2.9"] == ["COMMON_SUPPLY"]
    assert evidence["interface_catalog_sha256"] == [fault["catalog_sha256"]]
    assert fault["catalog_sha256"] != ""
    assert fault["kicad_version"] == version
    assert_connector_result_sources(
        results,
        version,
        ("reviewed-supply-domain-sharing-fault",),
    )


def assert_mapped_supply_domain_sharing_controls(results, version):
    same_domain_common_net = results["connector-return-fixture/reviewed-supply-control"]
    distinct_domain_separate_nets = results[
        "connector-return-fixture/reviewed-supply-domain-control"
    ]
    for result in (same_domain_common_net, distinct_domain_separate_nets):
        assert result["status"] == "PASS"
        assert result["coverage_status"] == "COMPLETE"
        assert result["lint_status"] == "PASS"
        assert result["findings"] == "none"
        assert result["repeatable"] == "true"
        assert result["kicad_version"] == version
    assert_connector_result_sources(
        results,
        version,
        ("reviewed-supply-control", "reviewed-supply-domain-control"),
    )
