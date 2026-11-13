"""Focused pytest nodes for omitted native edge-clearance scopes."""

from __future__ import annotations

PCB_SIGNAL_PATH_UNMAPPED_EDGE_CLEARANCE_RULE_NODE_CASES = (
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_pcb_signal_path_unmapped_edge_clearance_rules.py::"
            "test_unmapped_exact_edge_clearance_rule_for_source_net_is_reviewed"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_pcb_signal_path_unmapped_edge_clearance_rules.py::"
            "test_mapped_or_source_absent_edge_clearance_net_is_quiet"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_pcb_signal_path_unmapped_edge_clearance_rules.py::"
            "test_nonliteral_edge_clearance_scopes_are_not_guessed"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_pcb_signal_path_unmapped_edge_clearance_rules.py::"
            "test_length_and_edge_clearance_overrides_are_independent"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_pcb_signal_path_unmapped_edge_clearance_rules.py::"
            "test_edge_clearance_candidate_order_is_stable_under_rule_and_map_order"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        (
            "tests/test_design_lint_mcp_parity_pcb_signal_path_unmapped_edge_clearance.py::"
            "test_unmapped_edge_clearance_scope_matches_cli_and_mcp"
        ),
    ),
    (
        "pcb.signal_path_unmapped_edge_clearance_rule",
        "tests/test_pcb_signal_path_native.py::test_native_signal_path_drc_faults_are_repeatable",
    ),
)
