"""Keep custom DRC source-rule selectors focused on their own tests."""

from __future__ import annotations

import pytest

from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.architecture,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
]

RULE_NODE_CASES = (
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_pcb_dru_malformed_conditions.py::test_malformed_single_condition_clause_requests_source_bound_review",
    ),
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_pcb_dru_malformed_conditions.py::test_well_shaped_and_unconditional_rules_stay_quiet",
    ),
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_pcb_dru_malformed_conditions.py::test_text_variable_rule_is_deferred_to_existing_review",
    ),
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_pcb_dru_malformed_conditions.py::test_source_scope_policy_and_freshness_are_exact",
    ),
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_design_lint_mcp_parity_pcb_dru_malformed_condition.py::test_custom_drc_malformed_condition_matches_between_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_malformed_condition_clause",
        "tests/test_pcb_dru_malformed_conditions_native.py::test_condition_shape_faults_suppress_native_rules_but_controls_match_repeatably",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_pcb_dru_unknown_constraint.py::test_misspelled_constraint_requests_source_bound_review",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_pcb_dru_unknown_constraint.py::test_documented_and_legacy_constraint_names_stay_quiet",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_pcb_dru_unknown_constraint.py::test_unresolved_text_variables_and_out_of_scope_versions_are_quiet",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_pcb_dru_unknown_constraint.py::test_policy_fingerprint_and_source_freshness_are_exact",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_design_lint_mcp_parity_pcb_dru_unknown_constraint.py::test_unknown_custom_drc_constraint_matches_between_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_unknown_constraint_type",
        "tests/test_pcb_dru_unknown_constraint_native.py::test_misspelled_constraint_is_silently_skipped_and_control_is_repeatable",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_pcb_dru_malformed_bounds.py::test_unparseable_bounds_request_source_bound_review",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_pcb_dru_malformed_bounds.py::test_supported_bound_forms_are_quiet",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_pcb_dru_malformed_bounds.py::test_text_variables_and_layer_only_issues_stay_out_of_bound_review",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_pcb_dru_malformed_bounds.py::test_source_scope_policy_and_freshness_are_exact",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_design_lint_mcp_parity_pcb_dru_malformed_bounds.py::test_custom_drc_malformed_bounds_match_between_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_malformed_constraint_bounds",
        "tests/test_pcb_dru_malformed_bounds_native.py::test_repeated_bound_native_probe_is_repeatable_and_matches_control",
    ),
    (
        "pcb.custom_drc_contradictory_constraint_bounds",
        "tests/test_pcb_dru_contradictory_bounds.py::test_minimum_above_maximum_requests_one_source_bound_review_per_constraint",
    ),
    (
        "pcb.custom_drc_contradictory_constraint_bounds",
        "tests/test_pcb_dru_contradictory_bounds.py::test_valid_or_ambiguous_bounds_stay_quiet",
    ),
    (
        "pcb.custom_drc_contradictory_constraint_bounds",
        "tests/test_pcb_dru_contradictory_bounds.py::test_supported_scope_source_binding_and_review_policy_are_exact",
    ),
    (
        "pcb.custom_drc_contradictory_constraint_bounds",
        "tests/test_design_lint_mcp_parity_pcb_dru_contradictory_bounds.py::test_contradictory_custom_drc_bounds_match_between_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_contradictory_constraint_bounds",
        "tests/test_pcb_dru_contradictory_bounds_native.py::test_contradictory_bounds_are_accepted_and_produce_native_width_findings_repeatably",
    ),
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_pcb_dru_conflicting_severities.py::test_conflicting_direct_severities_request_source_bound_review",
    ),
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_design_lint_mcp_parity_pcb_dru_conflicting_severities.py::test_conflicting_custom_drc_severity_review_matches_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_conflicting_severities",
        "tests/test_pcb_dru_conflicting_severities_native.py::test_multiple_and_single_severity_rules_reach_native_sentinel",
    ),
    (
        "pcb.custom_drc_casefold_rule_name_collision",
        "tests/test_pcb_dru_casefold_rule_name_collisions.py::test_distinct_casefolded_names_request_source_bound_review_per_group",
    ),
    (
        "pcb.custom_drc_casefold_rule_name_collision",
        "tests/test_design_lint_mcp_parity_pcb_dru_casefold_rule_name.py::test_casefold_rule_name_review_matches_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_pcb_dru_layer_reference.py::test_display_aliases_in_layer_clauses_and_conditions_request_review",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_pcb_dru_layer_reference.py::test_canonical_names_and_alias_text_in_comments_are_quiet",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_pcb_dru_layer_reference.py::test_text_variables_defer_to_the_existing_substitution_review",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_pcb_dru_layer_reference.py::test_source_hashes_fingerprints_and_project_policy_are_exact",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_design_lint_mcp_parity_pcb_dru_layer_reference.py::test_custom_drc_layer_review_matches_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_layer_reference",
        "tests/test_pcb_dru_layer_reference_native.py::test_native_layer_name_faults_and_controls_on_pinned_kicad_1008",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_pcb_dru_deprecated_condition_functions.py::test_deprecated_calls_are_reported_once_per_named_rule",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_pcb_dru_deprecated_condition_functions.py::test_current_functions_strings_comments_and_no_condition_are_quiet",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_pcb_dru_deprecated_condition_functions.py::test_text_variable_sources_are_deferred_and_exact_version_is_required",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_pcb_dru_deprecated_condition_functions.py::test_source_binding_determinism_and_policy_are_exact",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_design_lint_mcp_parity_pcb_dru_deprecated_condition_functions.py::test_deprecated_custom_drc_function_review_matches_cli_and_mcp",
    ),
    (
        "pcb.custom_drc_deprecated_condition_function",
        "tests/test_pcb_dru_deprecated_condition_functions_native.py::test_deprecated_and_replacement_calls_reach_native_sentinel_on_kicad_1008",
    ),
)


def test_custom_drc_selector_collects_only_registered_rule_tests() -> None:
    rule_ids = tuple(sorted({rule_id for rule_id, _ in RULE_NODE_CASES}))
    result = collect_rule_nodes(rule_ids)

    assert result.returncode == 0, result.stdout + result.stderr
    for _, expected_node in RULE_NODE_CASES:
        assert expected_node in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout
