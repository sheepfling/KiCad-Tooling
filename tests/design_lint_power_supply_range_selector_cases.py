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
)
