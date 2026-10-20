"""CLI/MCP parity fixture references for named contacts left open."""

FOOTPRINT_NAMED_ALL_OPEN_FIXTURES = {
    "connector.footprint_named_power_input_all_open": {
        "fault_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_power_output_all_open": {
        "fault_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_signal_all_open": {
        "fault_fixtures": (
            "tests.test_connector_footprint_named_signal_all_open.test_named_signal_open_on_every_alias_is_reviewed_with_common_anchor",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_named_signal_all_open.test_unanchored_and_ineligible_contacts_do_not_become_findings",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
}
