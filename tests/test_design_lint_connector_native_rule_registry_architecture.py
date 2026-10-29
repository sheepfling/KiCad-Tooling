"""Keep connector native fault/control cases linked from active lint rules."""

from __future__ import annotations

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.architecture]


def test_connector_rules_catalogue_the_exact_native_fault_control_cases() -> None:
    expected_cases_by_rule = {
        "connector.repeated_pin_function": {
            "tests.test_native_db9_return_contracts.test_native_db9_return_contracts_are_source_bound_and_repeatable",
            "tests.test_native_db9_return_contracts.test_db9_return_lane_exports_only_fault_and_control",
        },
        "net.numbered_returns": {
            "tests.test_numbered_return_native_fixture_lane.test_native_numbered_pwm_return_fault_and_control_are_focused_and_repeatable",
            "tests.test_numbered_return_native_fixture_lane.test_native_ret_return_label_fault_and_control_are_focused_and_repeatable",
        },
        "net.return_labels_without_pin_roles": {
            "tests.test_numbered_return_native_fixture_lane.test_native_ret_return_label_fault_and_control_are_focused_and_repeatable",
        },
        "connector.peer_pin_assignment_outlier": {
            "tests.test_ci_hosted_connector_returns.test_peer_pin_assignments_and_offboard_scope",
        },
        "connector.peer_pin_assignment_divergence": {
            "tests.test_ci_hosted_connector_returns.test_peer_pin_assignments_and_offboard_scope",
        },
        "connector.generic_peer_pin_all_open": {
            "tests.test_ci_hosted_connector_returns.test_peer_pin_assignments_and_offboard_scope",
        },
        "connector.return_pin_on_positive_rail": {
            "tests.test_ci_hosted_connector_returns.test_return_pin_on_positive_rail",
        },
        "connector.unconnected_supply_pin": {
            "tests.test_ci_hosted_connector_returns.test_native_unconnected_named_connector_supply_pin_cases_repeat",
        },
        "connector.unconnected_return_pin": {
            "tests.test_ci_hosted_connector_returns.test_native_unconnected_named_connector_return_pin_cases_repeat",
        },
        "connector.mapped_supply_domains_share_net": {
            "tests.test_ci_hosted_connector_returns.test_mapped_supply_domains_shared_net_fault",
        },
        "connector.unconnected_power_output": {
            "tests.test_connector_unconnected_power_output.test_generic_connector_power_output_fault_and_control_on_pinned_native_versions",
        },
        "connector.footprint_peer_pin_all_open": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_all_open_peer_is_validated_on_pinned_native_versions",
        },
        "connector.footprint_peer_pin_assignment_divergence": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_peer_assignments_are_validated_on_pinned_native_versions",
        },
        "connector.footprint_peer_pin_open_outlier": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_open_peer_is_validated_on_pinned_native_versions",
        },
        "connector.footprint_named_power_input_all_open": {
            "tests.test_connector_footprint_named_power_input_all_open_native_fixture_lane.test_native_named_power_input_all_open_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_power_input_assignment_divergence": {
            "tests.test_connector_footprint_named_power_input_native_fixture_lane.test_native_named_power_input_divergence_fault_and_control_are_repeatable",
        },
        "connector.stateful_contact_topology_mismatch": {
            "tests.test_connector_stateful_contacts.test_native_stateful_contact_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_power_input_open_outlier": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_open_peer_is_validated_on_pinned_native_versions",
        },
        "connector.footprint_named_power_output_all_open": {
            "tests.test_connector_footprint_named_power_output_all_open_native_fixture_lane.test_native_named_power_output_all_open_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_power_output_assignment_divergence": {
            "tests.test_connector_footprint_named_power_output_native_fixture_lane.test_native_named_power_output_divergence_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_power_output_open_outlier": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_open_peer_is_validated_on_pinned_native_versions",
        },
        "connector.footprint_named_signal_all_open": {
            "tests.test_connector_footprint_named_signal_all_open_native_fixture_lane.test_native_named_signal_all_open_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_signal_assignment_divergence": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_named_signal_divergence_is_validated_on_pinned_native_versions",
        },
        "connector.footprint_named_signal_input_open_outlier": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_peer_assignments_are_validated_on_pinned_native_versions",
        },
        "connector.footprint_named_signal_output_open_outlier": {
            "tests.test_ci_hosted_connector_returns.test_footprint_alias_open_peer_is_validated_on_pinned_native_versions",
        },
        "connector.mapped_interface_signal_unassigned": {
            "tests.test_connector_mapped_interface_signal_unassigned.test_native_mapped_signal_pin_fault_and_control_are_repeatable",
        },
        "connector.mapped_interface_shield_unassigned": {
            "tests.test_connector_mapped_interface_shield_unassigned.test_native_mapped_shield_contact_fault_and_control_are_repeatable",
        },
        "connector.mapped_interface_shield_on_return_net": {
            "tests.test_connector_mapped_interface_shield_on_return_net_native_fixture_lane.test_native_mapped_shield_on_ret_is_reviewed_and_return_role_is_control",
        },
        "connector.mapped_interface_shield_on_supply_rail": {
            "tests.test_connector_mapped_interface_shield_on_supply_rail_native_fixture_lane.test_native_mapped_shield_on_supply_rail_fault_and_supply_role_control",
        },
        "connector.mapped_interface_other_unassigned": {
            "tests.test_connector_mapped_interface_other_unassigned.test_native_other_contact_fault_and_control_are_repeatable",
        },
        "connector.mapped_signals_share_net": {
            "tests.test_connector_mapped_signals_share_net_native_fixture_lane.test_native_shared_net_is_reviewed_only_for_distinct_mapped_signals",
        },
        "connector.mapped_shield_signal_share_net": {
            "tests.test_connector_mapped_signals_share_net_native_fixture_lane.test_native_shared_net_is_reviewed_only_for_distinct_mapped_signals",
        },
        "connector.mapped_signal_return_share_net": {
            "tests.test_connector_mapped_signals_share_net_native_fixture_lane.test_native_shared_net_is_reviewed_only_for_distinct_mapped_signals",
        },
        "connector.mapped_signals_split_nets": {
            "tests.test_connector_mapped_signals_split_nets_native_fixture_lane.test_native_split_nets_are_reviewed_only_for_repeated_mapped_signal",
        },
        "connector.mapped_interface_other_named_rail": {
            "tests.test_connector_mapped_interface_other_named_rail_native_fixture_lane.test_native_single_other_pin_on_ret_is_reviewed_and_role_control_is_clean",
        },
        "connector.mapped_interface_supply_on_return_net": {
            "tests.test_connector_mapped_interface_supply_on_return_net_native_fixture_lane.test_native_generic_supply_map_on_ret_is_reviewed_and_return_role_is_control",
        },
        "connector.mapped_interface_signal_on_named_rail": {
            "tests.test_connector_mapped_interface_signal_on_named_rail_native_fixture_lane.test_native_generic_signal_map_on_ret_is_reviewed_and_return_role_is_control",
        },
        "connector.mapped_interface_power_contact_unassigned": {
            "tests.test_connector_mapped_interface_power_contact_unassigned.test_native_mapped_power_contact_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_signal_mode_dependent_open_outlier": {
            "tests.test_connector_footprint_named_signal_mode_dependent_open_native_fixture_lane.test_native_mode_dependent_signal_fault_and_control_are_repeatable",
        },
        "connector.footprint_named_passive_open_outlier": {
            "tests.test_connector_footprint_named_passive_open_native_fixture_lane.test_native_named_passive_open_fault_control_repeatable",
        },
        "connector.footprint_named_passive_assignment_divergence": {
            "tests.test_connector_footprint_named_passive_divergence_native_fixture_lane.test_native_named_passive_divergence_fault_and_control_are_repeatable",
        },
        "connector.footprint_peer_pin_metadata_assignment_divergence": {
            "tests.test_connector_footprint_peer_metadata_native_fixture_lane.test_native_metadata_divergence_fault_and_control_are_repeatable",
        },
        "connector.footprint_peer_pin_missing_metadata_assignment_divergence": {
            "tests.test_connector_footprint_peer_missing_metadata_native_fixture_lane.test_native_missing_metadata_fault_and_control_are_repeatable",
        },
        "connector.footprint_peer_pin_missing_metadata_open_outlier": {
            "tests.test_connector_footprint_peer_missing_metadata_open_native_fixture_lane.test_native_open_metadata_fault_and_control_are_repeatable",
        },
        "connector.footprint_peer_pin_metadata_open_outlier": {
            "tests.test_connector_footprint_peer_metadata_open_native_fixture_lane.test_native_metadata_open_fault_and_control_are_repeatable",
        },
        "connector.unconnected_power_input": {
            "tests.test_ci_hosted_connector_returns.test_power_pin_and_reviewed_role_cases",
        },
        "component.unconnected_power_input": {
            "tests.test_component_power_input_native_fixture_lane.test_native_generic_component_power_input_cases_are_focused_and_repeatable",
        },
        "component.unconnected_supply_pin": {
            "tests.test_component_named_supply_pin_native_fixture_lane.test_native_named_component_supply_pin_fault_and_control_are_focused_and_repeatable",
        },
        "component.unconnected_return_pin": {
            "tests.test_component_named_return_pin_native_fixture_lane.test_native_named_component_return_pin_fault_and_control_are_focused_and_repeatable",
        },
        "component.repeated_return_pin_function": {
            "tests.test_component_named_return_pin_native_fixture_lane.test_native_named_component_return_pin_fault_and_control_are_focused_and_repeatable",
        },
        "component.peer_power_input_assignment_divergence": {
            "tests.test_component_peer_power_input_native_fixture_lane.test_native_generic_peer_power_input_fault_and_control_are_repeatable",
        },
        "component.peer_power_input_open_assignment": {
            "tests.test_component_peer_power_input_native_fixture_lane.test_native_named_peer_power_input_open_fault_and_control_are_repeatable",
        },
        "component.peer_power_input_named_assignment_divergence": {
            "tests.test_component_peer_power_input_native_fixture_lane.test_native_named_peer_power_input_divergence_fault_and_control_are_repeatable",
        },
        "component.peer_power_input_named_all_open": {
            "tests.test_component_named_peer_power_input_all_open_native.test_native_named_peer_power_input_all_open_fault_and_control_are_repeatable",
        },
        "connector.peer_power_input_open_assignment": {
            "tests.test_connector_named_power_input_native_fixture_lane.test_native_connector_named_power_input_alias_fault_and_control_are_repeatable",
        },
        "connector.peer_power_input_named_all_open": {
            "tests.test_connector_named_power_input_native_fixture_lane.test_native_connector_named_power_input_alias_fault_and_control_are_repeatable",
        },
        "connector.peer_power_input_named_assignment_divergence": {
            "tests.test_connector_named_power_input_native_fixture_lane.test_native_connector_named_power_input_alias_fault_and_control_are_repeatable",
        },
        "connector.peer_power_output_open_assignment": {
            "tests.test_connector_named_power_output_native_fixture_lane.test_native_connector_named_power_output_alias_fault_and_control_are_repeatable",
        },
        "connector.peer_power_output_named_all_open": {
            "tests.test_connector_named_power_output_native_fixture_lane.test_native_connector_named_power_output_alias_fault_and_control_are_repeatable",
        },
        "connector.peer_power_output_named_assignment_divergence": {
            "tests.test_connector_named_power_output_native_fixture_lane.test_native_connector_named_power_output_alias_fault_and_control_are_repeatable",
        },
        "component.generic_peer_pin_assignment_outlier": {
            "tests.test_component_peer_pin_assignment_native_fixture_lane.test_native_generic_peer_assignment_outlier_fault_and_control_are_repeatable",
        },
        "power.named_supply_pin_on_negative_rail": {
            "tests.test_power_pin_net_role_native_fixture_lane.test_named_supply_pin_on_negative_rail_fault_and_control_export_repeatably",
        },
        "net.numbered_power_rails": {
            "tests.test_ci_hosted_connector_returns.test_power_pin_and_reviewed_role_cases",
        },
    }
    rules = {rule.rule_id: rule for rule in rule_catalog().rules}
    expected_control_cases_by_rule = {
        "connector.mapped_supply_domains_share_net": {
            "tests.test_ci_hosted_connector_returns.test_mapped_supply_domains_shared_net_valid_controls",
        },
    }
    connector_native_rules = {
        rule_id
        for rule_id, rule in rules.items()
        if "KICAD_RUN_NATIVE_CONNECTOR_FIXTURES" in rule.required_native_fixtures
    }
    missing_connector_cases = connector_native_rules - set(expected_cases_by_rule)
    assert not missing_connector_cases, (
        "Connector rules requiring native acceptance must catalogue their exact fault/control "
        f"test cases: {sorted(missing_connector_cases)}"
    )
    native_fixture_by_rule = {
        rule_id: "KICAD_RUN_NATIVE_CONNECTOR_FIXTURES" for rule_id in expected_cases_by_rule
    }
    native_fixture_by_rule["connector.repeated_pin_function"] = (
        "KICAD_RUN_NATIVE_DB9_RETURN_CONTRACT_FIXTURES"
    )
    native_fixture_by_rule["component.unconnected_supply_pin"] = (
        "KICAD_RUN_NATIVE_COMPONENT_NAMED_SUPPLY_PIN_FIXTURES"
    )
    native_fixture_by_rule["component.unconnected_return_pin"] = (
        "KICAD_RUN_NATIVE_COMPONENT_NAMED_RETURN_PIN_FIXTURES"
    )
    native_fixture_by_rule["component.repeated_return_pin_function"] = (
        "KICAD_RUN_NATIVE_COMPONENT_NAMED_RETURN_PIN_FIXTURES"
    )
    native_fixture_by_rule["component.peer_power_input_assignment_divergence"] = (
        "KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES"
    )
    native_fixture_by_rule["component.peer_power_input_open_assignment"] = (
        "KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES"
    )
    native_fixture_by_rule["component.peer_power_input_named_assignment_divergence"] = (
        "KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES"
    )
    native_fixture_by_rule["component.peer_power_input_named_all_open"] = (
        "KICAD_RUN_NATIVE_COMPONENT_PEER_POWER_INPUT_FIXTURES"
    )
    native_fixture_by_rule["component.generic_peer_pin_assignment_outlier"] = (
        "KICAD_RUN_NATIVE_COMPONENT_PEER_PIN_FIXTURES"
    )
    native_fixture_by_rule["power.named_supply_pin_on_negative_rail"] = (
        "KICAD_RUN_NATIVE_POWER_PIN_NET_ROLE_FIXTURES"
    )
    for rule_id, expected_cases in expected_cases_by_rule.items():
        rule = rules[rule_id]
        assert native_fixture_by_rule[rule_id] in rule.required_native_fixtures
        assert expected_cases <= set(rule.fault_fixtures)
        expected_controls = expected_control_cases_by_rule.get(rule_id, expected_cases)
        assert expected_controls <= set(rule.valid_control_fixtures)
