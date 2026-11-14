from types import MappingProxyType

"""CLI/MCP parity fixture references for footprint-alias peer rules."""

FOOTPRINT_PEER_PARITY_FIXTURES = MappingProxyType(
    {
        "connector.footprint_peer_unanchored_scope_coverage_missing": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_peer_unanchored_coverage_parity.test_unanchored_partial_open_connector_coverage_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_peer_unanchored_coverage_parity.test_unanchored_partial_open_connector_coverage_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_passive_assignment_divergence": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_named_passive_divergence_parity.test_named_passive_divergence_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_named_passive_divergence_parity.test_named_passive_divergence_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_input_all_open": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_power_output_all_open": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_peer_generic_power_pin_all_open": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_all_open.test_generic_power_contact_open_on_all_alias_peers_is_opt_in_review",
                    "tests.test_design_lint_mcp_parity_connector_generic_power_all_open.test_generic_power_contact_cli_mcp_fault_and_control_parity",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_all_open.test_assigned_or_meaningfully_named_power_contacts_are_controls",
                    "tests.test_connector_footprint_peer_generic_power_all_open.test_inconsistent_pin_metadata_and_separately_scoped_peers_stay_quiet",
                    "tests.test_design_lint_mcp_parity_connector_generic_power_all_open.test_generic_power_contact_cli_mcp_fault_and_control_parity",
                ),
                "metamorphic_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_all_open.test_peer_power_review_fingerprint_is_stable_under_mapping_order",
                ),
            }
        ),
        "connector.footprint_peer_generic_power_pin_open_outlier": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_partial_open.test_generic_power_partial_open_peer_pattern_is_opt_in_review",
                    "tests.test_design_lint_mcp_parity_connector_generic_power_partial_open.test_generic_power_partial_open_cli_mcp_fault_and_control_parity",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_partial_open.test_common_assigned_and_documented_open_contacts_are_controls",
                    "tests.test_connector_footprint_peer_generic_power_partial_open.test_unanchored_partial_open_needs_current_shared_peer_scope",
                    "tests.test_design_lint_mcp_parity_connector_generic_power_partial_open.test_generic_power_partial_open_cli_mcp_fault_and_control_parity",
                ),
                "metamorphic_fixtures": (
                    "tests.test_connector_footprint_peer_generic_power_partial_open.test_power_peer_open_fingerprint_is_stable_under_mapping_order",
                ),
            }
        ),
        "connector.footprint_named_signal_all_open": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_named_signal_all_open.test_named_signal_open_on_every_alias_is_reviewed_with_common_anchor",
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_named_signal_all_open.test_unanchored_and_ineligible_contacts_do_not_become_findings",
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_signal_mode_dependent_open_outlier": MappingProxyType(
            {
                "fault_fixtures": (
                    "tests.test_connector_footprint_named_signal_mode_dependent_open.test_mode_dependent_signal_open_on_one_alias_is_reviewed",
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
                "valid_control_fixtures": (
                    "tests.test_connector_footprint_named_signal_mode_dependent_open.test_common_unanchored_and_ineligible_contacts_are_not_mode_dependent_findings",
                    "tests.test_connector_footprint_peer_parity.test_footprint_alias_review_matches_cli_and_mcp",
                ),
            }
        ),
        "connector.footprint_named_passive_open_outlier": MappingProxyType(
            {
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
            }
        ),
    }
)
