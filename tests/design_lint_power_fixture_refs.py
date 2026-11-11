"""Catalogued fault and control references for power lint rules."""

from types import MappingProxyType

OPEN_DRAIN_CONTROL_PARITY_FIXTURES = MappingProxyType(
    {
        "power.open_drain_control_input_pullup_voltage_review": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_open_drain_control_voltage.test_open_collector_control_pullup_to_different_supply_requests_review",
                    "tests.test_open_drain_control_voltage.test_pullup_voltage_review_adds_detection_over_existing_bias_checks",
                    "tests.test_open_drain_control_voltage_native_fixture_lane.test_native_open_drain_control_fault_and_control",
                    "tests.test_design_lint_mcp_parity_open_drain_control_voltage.test_open_drain_control_fault_and_control_match_cli_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_open_drain_control_voltage.test_equal_or_ambiguous_cases_remain_quiet",
                    "tests.test_open_drain_control_voltage.test_pullup_voltage_review_adds_detection_over_existing_bias_checks",
                    "tests.test_open_drain_control_voltage_native_fixture_lane.test_native_open_drain_control_fault_and_control",
                    "tests.test_design_lint_mcp_parity_open_drain_control_voltage.test_open_drain_control_fault_and_control_match_cli_mcp",
                ),
                "metamorphic_fixtures": (
                    "tests.test_open_drain_control_voltage.test_open_drain_control_fingerprint_is_stable_under_mapping_reordering",
                    "tests.test_open_drain_control_voltage.test_rule_policy_can_block_disable_or_ignore_exact_finding",
                ),
            }
        ),
    }
)

SUPPLY_RANGE_MAP_COVERAGE_PARITY_FIXTURES = MappingProxyType(
    {
        "power.component_supply_range_map_coverage": MappingProxyType(
            {
                "fault_fixtures": (
                    (
                        "tests.test_component_supply_range_map_coverage_parity."
                        "test_component_supply_range_map_coverage_review_matches_between_cli_and_mcp"
                    ),
                ),
            }
        ),
    }
)
