"""Focused pytest nodes for omitted native fromTo length scopes."""

from __future__ import annotations

PCB_SIGNAL_PATH_UNMAPPED_FROM_TO_RULE_NODE_CASES = (
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_pcb_signal_path_unmapped_fromto_rules.py::"
            "test_unmapped_exact_from_to_length_pair_is_reviewed"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_pcb_signal_path_unmapped_fromto_rules.py::"
            "test_mapped_pair_in_either_order_and_split_source_nets_are_quiet"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_pcb_signal_path_unmapped_fromto_rules.py::"
            "test_wildcard_compound_and_variable_from_to_scopes_are_not_guessed"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_pcb_signal_path_unmapped_fromto_rules.py::"
            "test_from_to_mode_is_independent_and_coverage_off_skips_evidence"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_pcb_signal_path_unmapped_fromto_rules.py::"
            "test_candidate_order_is_stable_and_repeated_rule_pairs_are_grouped"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        (
            "tests/test_design_lint_mcp_parity_pcb_signal_path_unmapped_fromto.py::"
            "test_unmapped_exact_from_to_length_scope_matches_cli_and_mcp"
        ),
    ),
    (
        "pcb.signal_path_unmapped_from_to_length_rule",
        "tests/test_pcb_signal_path_native.py::test_native_signal_path_drc_faults_are_repeatable",
    ),
)
