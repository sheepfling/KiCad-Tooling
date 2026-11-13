"""Focused pytest nodes for unmatched exact-net custom DRC scopes."""

from __future__ import annotations

PCB_EXACT_NET_SCOPE_RULE_NODE_CASES = (
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope.py::test_exact_net_selector_missing_from_board_is_reviewed_with_native_evidence",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope.py::test_current_net_names_and_unsupported_condition_shapes_are_quiet",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope.py::test_scanner_runs_for_pcb_only_and_skips_unsupported_or_disabled_inputs",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope.py::test_malformed_board_net_inventory_does_not_create_a_stale_scope_finding",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope.py::test_rule_order_does_not_change_grouping_or_subject_order",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_design_lint_mcp_parity_pcb_drc_exact_net_scope.py::test_unmatched_exact_net_scope_matches_between_cli_and_mcp",
    ),
    (
        "pcb.drc_exact_net_scope_unmatched",
        "tests/test_pcb_drc_exact_net_scope_native.py::test_exact_net_selector_case_semantics_are_deterministic",
    ),
)
