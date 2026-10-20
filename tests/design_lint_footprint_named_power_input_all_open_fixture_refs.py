"""CLI/MCP parity fixture references for named footprint-alias power inputs."""

FOOTPRINT_NAMED_POWER_INPUT_ALL_OPEN_FIXTURES = {
    "connector.footprint_named_power_input_all_open": {
        "fault_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
}
