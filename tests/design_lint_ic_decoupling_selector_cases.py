"""Focused node inventory for IC decoupling-map pin-coverage lint."""

RULE_ID = "power.ic_decoupling_map_pin_coverage"
IC_DECOUPLING_MAP_COVERAGE_RULE_NODE_CASES = (
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_unmapped_native_power_input_pin_needs_review",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_incomplete_pin_metadata_needs_review",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_stale_map_identity_needs_review",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_complete_current_pin_map_is_quiet",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_dnp_non_ic_and_unmapped_ic_scope_are_not_candidates",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_requirement_order_does_not_change_issue_identity_or_order",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_pin_and_map_mapping_order_does_not_change_finding",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage.py::test_rule_is_opt_in_and_supports_review_block_off_and_exact_ignore",
    ),
    (
        RULE_ID,
        "tests/test_ic_decoupling_map_pin_coverage_parity.py::test_ic_decoupling_map_pin_coverage_review_matches_between_cli_and_mcp",
    ),
    (
        RULE_ID,
        "tests/test_ic_rail_capacitor_native_fixture_lane.py::test_missing_capacitor_and_controls_export_repeatably",
    ),
)
