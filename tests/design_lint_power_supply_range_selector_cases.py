"""Focused selector cases for mapped component supply-range rules."""

from __future__ import annotations

POWER_SUPPLY_RANGE_RULE_NODE_CASES = (
    (
        "power.component_supply_voltage_outside_range",
        "tests/test_component_supply_voltage_range.py::test_supported_positive_voltage_label_below_range_needs_review",
    ),
    (
        "power.component_supply_voltage_outside_range",
        "tests/test_component_supply_voltage_range.py::test_supported_positive_voltage_inside_inclusive_range_is_quiet",
    ),
    (
        "power.component_supply_range_pin_coverage",
        "tests/test_component_supply_range_pin_coverage.py::test_unmapped_power_input_pin_needs_review",
    ),
    (
        "power.component_supply_range_pin_coverage",
        "tests/test_component_supply_range_pin_coverage.py::test_complete_component_supply_pin_map_is_quiet",
    ),
    (
        "power.component_supply_range_map_coverage",
        "tests/test_component_supply_range_map_coverage.py::test_unmapped_fitted_ic_supply_pins_need_review",
    ),
    (
        "power.component_supply_range_map_coverage",
        "tests/test_component_supply_range_map_coverage.py::test_complete_current_map_quiets_each_supported_ic",
    ),
    (
        "power.component_supply_range_map_coverage",
        "tests/test_component_supply_range_map_coverage_parity.py::test_component_supply_range_map_coverage_review_matches_between_cli_and_mcp",
    ),
)
