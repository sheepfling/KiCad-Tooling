"""Focused pytest nodes for omitted native signal-path length scopes."""

from __future__ import annotations

PCB_SIGNAL_PATH_UNMAPPED_RULE_NODE_CASES = (
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_unmapped_rules.py::test_unmapped_exact_length_rule_for_source_net_is_reviewed",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_unmapped_rules.py::test_mapped_or_source_absent_net_does_not_prompt",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_unmapped_rules.py::test_nonliteral_length_scope_is_not_guessed",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_unmapped_rules.py::test_map_coverage_and_rule_modes_gate_the_prompt",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_unmapped_rules.py::test_rule_and_map_order_do_not_change_candidate_order",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_design_lint_mcp_parity_pcb_signal_path_unmapped.py::test_unmapped_exact_length_scope_matches_cli_and_mcp",
    ),
    (
        "pcb.signal_path_unmapped_native_rule",
        "tests/test_pcb_signal_path_native.py::test_native_signal_path_drc_faults_are_repeatable",
    ),
)
