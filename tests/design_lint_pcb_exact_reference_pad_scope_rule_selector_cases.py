"""Focused pytest nodes for unmatched exact-reference/pad custom DRC scopes."""

from __future__ import annotations

PCB_EXACT_REFERENCE_PAD_SCOPE_RULE_NODE_CASES = (
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_pad_scope.py::test_absent_exact_pad_selector_is_reviewed_with_source_identity",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_pad_scope.py::test_casefolded_absent_pads_group_stably_and_existing_pad_is_a_control",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_pad_scope.py::test_unsupported_scopes_and_missing_footprints_stay_quiet",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_pad_scope.py::test_scan_skips_disabled_unsupported_and_non_pcb_requests_before_reading",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_design_lint_mcp_parity_pcb_drc_exact_reference_pad_scope.py::test_unmatched_exact_reference_pad_scope_matches_between_cli_and_mcp",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_pcb_drc_exact_reference_pad_scope_native.py::test_reference_pad_selector_behavior_is_version_bounded_and_deterministic",
    ),
    (
        "pcb.drc_exact_reference_pad_scope_unmatched",
        "tests/test_design_lint_architecture_pcb_drc_exact_reference_pad_scope.py::test_exact_reference_pad_scope_has_focused_inventory_predicate_and_scan",
    ),
)
