"""CLI/MCP parity fixture references for footprint-alias peer rules."""

FOOTPRINT_PEER_PARITY_FIXTURES = {
    "connector.footprint_named_passive_assignment_divergence": {
        "fault_fixtures": (
            "tests.test_connector_footprint_named_passive_divergence_parity.test_named_passive_divergence_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_named_passive_divergence_parity.test_named_passive_divergence_matches_cli_and_mcp",
        ),
    },
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
    "connector.footprint_named_signal_mode_dependent_open_outlier": {
        "fault_fixtures": (
            "tests.test_connector_footprint_named_signal_mode_dependent_open.test_mode_dependent_signal_open_on_one_alias_is_reviewed",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_named_signal_mode_dependent_open.test_common_unanchored_and_ineligible_contacts_are_not_mode_dependent_findings",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
        ),
    },
    "connector.footprint_named_passive_open_outlier": {
        "fault_fixtures": (
            "tests.test_connector_footprint_named_passive_open.test_named_passive_contact_open_on_one_alias_is_reviewed",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
            "tests.test_connector_footprint_named_passive_open_native_fixture_lane.test_named_passive_validator_checks_fault_and_control",
            "tests.test_connector_footprint_named_passive_open_native_fixture_lane.test_native_named_passive_open_fault_control_repeatable",
        ),
        "valid_control_fixtures": (
            "tests.test_connector_footprint_named_passive_open.test_unanchored_and_ineligible_passive_contacts_are_not_findings",
            "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
            "tests.test_connector_footprint_named_passive_open_native_fixture_lane.test_named_passive_validator_checks_fault_and_control",
            "tests.test_connector_footprint_named_passive_open_native_fixture_lane.test_native_named_passive_open_fault_control_repeatable",
        ),
        "metamorphic_fixtures": (
            "tests.test_connector_footprint_named_passive_open.test_named_passive_open_finding_is_stable_under_mapping_order",
        ),
    },
}
