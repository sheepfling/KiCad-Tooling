"""Supplemental parity fixture references for lint catalog rules."""

from __future__ import annotations

from types import MappingProxyType

from tests.design_lint_connector_return_parity_fixtures import (
    CONNECTOR_RETURN_PARITY_FIXTURES,
)
from tests.design_lint_ethernet_connector_parity_fixtures import (
    ETHERNET_CONNECTOR_PARITY_FIXTURES,
)
from tests.design_lint_footprint_peer_fixture_refs import (
    FOOTPRINT_PEER_PARITY_FIXTURES,
)
from tests.design_lint_power_fixture_refs import OPEN_DRAIN_CONTROL_PARITY_FIXTURES
from tests.design_lint_swd_generic_connector_parity_fixtures import (
    SWD_GENERIC_CONNECTOR_PARITY_FIXTURES,
)
from tests.design_lint_swd_signal_same_net_parity_fixtures import (
    SWD_SIGNAL_SAME_NET_PARITY_FIXTURES,
)


def _refs(owner: str, *tests: str) -> tuple[str, ...]:
    return tuple(f"{owner}.{name}" for name in tests)


_PARITY_FIXTURES_BY_RULE = MappingProxyType(
    {
        **FOOTPRINT_PEER_PARITY_FIXTURES,
        **OPEN_DRAIN_CONTROL_PARITY_FIXTURES,
        **CONNECTOR_RETURN_PARITY_FIXTURES,
        **ETHERNET_CONNECTOR_PARITY_FIXTURES,
        **SWD_GENERIC_CONNECTOR_PARITY_FIXTURES,
        **SWD_SIGNAL_SAME_NET_PARITY_FIXTURES,
        "bus.i2c_missing_pullup": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
                    "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
                    "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
                ),
            }
        ),
        "bus.serial_unmapped_peer": MappingProxyType(
            {
                "fault_fixtures": (
                    *_refs(
                        "tests.test_design_lint_i2c_parity.DesignLintI2cParityTests",
                        "test_mapped_array_control_and_missing_array_fault_match_cli_and_mcp",
                    ),
                    *_refs(
                        "tests.test_design_lint_serial_parity.DesignLintSerialParityTests",
                        "test_alternate_function_uart_labels_match_cli_and_mcp",
                    ),
                ),
            }
        ),
        "bus.usb_superspeed_generic_connector_pair_review": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_usb_superspeed_generic_connector",
                    "test_generic_superspeed_connector_cli_mcp_parity",
                ),
            }
        ),
        "bus.i3c_generic_connector_pair_review": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_i3c_generic_connector",
                    "test_generic_i3c_connector_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_i3c_generic_connector",
                    "test_generic_i3c_connector_cli_mcp_parity",
                ),
            }
        ),
        "component.peer_power_output_unconnected": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_power_output_unconnected_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_power_output_unconnected_lint_cli_mcp_parity",
                ),
            }
        ),
        "component.peer_signal_input_unconnected": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_signal_input_unconnected_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_signal_input_unconnected_lint_cli_mcp_parity",
                ),
            }
        ),
        "component.peer_signal_output_unconnected": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_signal_output_unconnected_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_signal_output_unconnected_lint_cli_mcp_parity",
                ),
            }
        ),
        "component.peer_bidirectional_pin_unconnected": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_peer_pins",
                    "test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
                ),
            }
        ),
        "component.two_pin_passive_same_net": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_mapped_custom_passive",
                    "test_mapped_custom_capacitor_same_net_lint_cli_mcp_parity",
                )
                + _refs(
                    "tests.test_design_lint_mcp_parity_two_pin_thermistors",
                    "test_same_net_thermistor_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_mapped_custom_passive",
                    "test_mapped_custom_capacitor_same_net_lint_cli_mcp_parity",
                )
                + _refs(
                    "tests.test_design_lint_mcp_parity_two_pin_thermistors",
                    "test_same_net_thermistor_lint_cli_mcp_parity",
                ),
            }
        ),
        "component.unconnected_power_output": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_unconnected_power_output",
                    "test_generic_power_output_review_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_unconnected_power_output",
                    "test_generic_power_output_review_cli_mcp_parity",
                ),
            }
        ),
        "connector.generic_peer_pin_all_open": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_all_open",
                    "test_all_open_generic_peer_pin_lint_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_all_open",
                    "test_all_open_generic_peer_pin_lint_cli_mcp_parity",
                ),
            }
        ),
        "connector.generic_peer_pin_open_outlier": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_numeric_peer_open",
                    "test_numeric_peer_open_lint_matches_between_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_numeric_peer_open",
                    "test_numeric_peer_open_lint_matches_between_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_peer_pin_all_open": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_peer_open",
                    "test_all_generic_contacts_open_across_footprint_aliases_is_opt_in_review",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                )
                + _refs(
                    "tests.test_design_lint_mcp_parity_connector_all_open",
                    "test_unanchored_footprint_alias_prompt_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_peer_open",
                    "test_all_open_footprint_alias_requires_a_shared_anchor_and_eligible_generic_metadata",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "metamorphic_fixtures": _refs(
                    "tests.test_connector_footprint_peer_open",
                    "test_all_open_footprint_alias_is_stable_under_mapping_order",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_input_open_outlier": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_signal_input_open_outlier": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_output_open_outlier": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_signal_output_open_outlier": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_signal_assignment_divergence": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_named_signal_divergence",
                    "test_named_signal_pin_on_different_nets_is_reviewed_with_a_common_anchor",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_named_signal_divergence",
                    "test_common_unanchored_or_ineligible_contacts_are_not_signal_divergence_findings",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_input_assignment_divergence": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_input_divergence",
                    "test_named_power_input_on_different_nets_is_reviewed_with_a_common_anchor",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                )
                + _refs(
                    "tests.test_connector_footprint_named_power_input_native_fixture_lane",
                    "test_native_named_power_input_divergence_fault_and_control_are_repeatable",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_input_divergence",
                    "test_common_unanchored_or_ineligible_contacts_are_not_power_divergence_findings",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                )
                + _refs(
                    "tests.test_connector_footprint_named_power_input_native_fixture_lane",
                    "test_native_named_power_input_divergence_fault_and_control_are_repeatable",
                ),
                "metamorphic_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_input_divergence",
                    "test_named_power_input_divergence_is_stable_under_mapping_order",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_output_assignment_divergence": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_output_divergence",
                    "test_named_power_output_on_different_nets_is_reviewed_with_a_common_anchor",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                )
                + _refs(
                    "tests.test_connector_footprint_named_power_output_native_fixture_lane",
                    "test_native_named_power_output_divergence_fault_and_control_are_repeatable",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_output_divergence",
                    "test_common_unanchored_or_ineligible_contacts_are_not_power_output_findings",
                )
                + _refs(
                    "tests.test_connector_footprint_peer_parity",
                    "test_footprint_alias_review_matches_cli_and_mcp",
                )
                + _refs(
                    "tests.test_connector_footprint_named_power_output_native_fixture_lane",
                    "test_native_named_power_output_divergence_fault_and_control_are_repeatable",
                ),
                "metamorphic_fixtures": _refs(
                    "tests.test_connector_footprint_named_power_output_divergence",
                    "test_named_power_output_divergence_is_stable_under_mapping_order",
                ),
            }
        ),
        "connector.unconnected_power_output": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_power_output",
                    "test_generic_connector_power_output_review_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_power_output",
                    "test_generic_connector_power_output_review_cli_mcp_parity",
                ),
            }
        ),
        "connector.unconnected_power_input": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_connector_coverage",
                    "test_design_lint_connector_coverage_and_review_lifecycle",
                )
                + _refs(
                    "tests.test_design_lint_power_pin_patterns.TestDesignLintPowerPinPatterns",
                    "test_power_input_aliases_use_typed_rule_instead_of_generic_all_open_hint",
                )
                + _refs(
                    "tests.test_connector_unconnected_power_input_native_fixture_lane",
                    "test_generic_connector_power_input_fault_and_control_are_focused_and_repeatable",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_power_pin_patterns.TestDesignLintPowerPinPatterns",
                    "test_power_input_aliases_use_typed_rule_instead_of_generic_all_open_hint",
                )
                + _refs(
                    "tests.test_connector_unconnected_power_input_native_fixture_lane",
                    "test_generic_connector_power_input_fault_and_control_are_focused_and_repeatable",
                ),
            }
        ),
        "power.named_supply_pin_on_negative_rail": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_power_pin_roles",
                    "test_named_supply_pin_on_negative_rail_cli_mcp_parity",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_power_pin_roles",
                    "test_named_supply_pin_on_negative_rail_cli_mcp_parity",
                ),
            }
        ),
        "power.ic_decoupling_below_project_minimum": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_ic_decoupling",
                    "test_ic_decoupling_review_matches_between_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_ic_decoupling",
                    "test_ic_decoupling_review_matches_between_cli_and_mcp",
                ),
            }
        ),
        "pcb.keepout_intent_coverage": MappingProxyType(
            {
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_keepouts_mcp_parity",
                    "test_disabled_keepout_coverage_matches_cli_and_mcp",
                ),
            }
        ),
        "pcb.rf_module_antenna_keepout_coverage": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_pcb_rf_antenna_mcp_parity",
                    "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    *_refs(
                        "tests.test_pcb_rf_antenna_mcp_parity",
                        "test_disabled_rf_antenna_coverage_matches_cli_and_mcp",
                    ),
                    *_refs(
                        "tests.test_pcb_rf_antenna_mcp_parity",
                        "test_enabled_rf_antenna_fault_and_control_match_cli_and_mcp",
                    ),
                ),
            }
        ),
        "pcb.signal_path_rule_coverage": MappingProxyType(
            {
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_signal_path_mcp_parity",
                    "test_disabled_signal_path_coverage_matches_cli_and_mcp",
                ),
            }
        ),
        "pcb.differential_pair_route_skew": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_pcb_differential_pair_route_skew",
                    "test_excessive_routed_skew_is_reviewed_against_authored_bound",
                    "test_missing_member_route_is_incomplete_not_clean",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_pcb_differential_pair_route_skew",
                    "test_route_skew_at_authored_boundary_is_within_limit",
                    "test_equal_routes_are_within_zero_skew_bound",
                ),
            }
        ),
        "oscillator.output_load_path_mismatch": MappingProxyType(
            {
                "fault_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_oscillator_output_paths",
                    "test_oscillator_output_path_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": _refs(
                    "tests.test_design_lint_mcp_parity_oscillator_output_paths",
                    "test_oscillator_output_path_matches_cli_and_mcp",
                ),
            }
        ),
    }
)
