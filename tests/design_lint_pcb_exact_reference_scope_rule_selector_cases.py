"""Focused pytest nodes for unmatched exact-reference custom DRC scopes."""

from __future__ import annotations

PCB_EXACT_REFERENCE_SCOPE_RULE_NODE_CASES = (
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope.py::test_absent_exact_selector_is_reviewed_with_bound_sources",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope.py::test_present_and_casefold_equivalent_selectors_are_quiet_or_grouped",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope.py::test_unsupported_shapes_ignored_constraints_and_ambiguous_inventory_stay_quiet",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope.py::test_candidate_support_is_limited_to_native_verified_kicad_version",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope.py::test_scan_skips_disabled_unsupported_and_non_pcb_requests_before_reading",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_design_lint_mcp_parity_pcb_drc_exact_reference_scope.py::test_unmatched_exact_reference_scope_matches_between_cli_and_mcp",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_scope_native.py::test_exact_reference_selector_behavior_is_version_bounded_and_deterministic",
    ),
    (
        "pcb.drc_exact_reference_scope_unmatched",
        "tests/test_design_lint_architecture_pcb_drc_exact_reference_scope.py::test_exact_reference_scope_has_focused_inventory_predicate_and_scan",
    ),
)
