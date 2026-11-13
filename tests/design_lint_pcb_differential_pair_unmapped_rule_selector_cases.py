"""Focused pytest nodes for unmapped differential-pair DRC scope review."""

from __future__ import annotations

PCB_DIFFERENTIAL_PAIR_UNMAPPED_RULE_NODE_CASES = (
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_exact_native_pair_selector_missing_from_map_is_reviewed",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_mapped_selector_and_non_pair_rules_are_quiet",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_nonliteral_or_compound_pair_conditions_are_skipped",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_disabled_rules_do_not_read_native_sources",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_missing_map_and_non_pcb_projects_do_not_read_native_sources",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_pcb_differential_pair_unmapped.py::test_native_rule_order_does_not_change_review_grouping",
    ),
    (
        "pcb.differential_pair_unmapped_native_rule",
        "tests/test_design_lint_mcp_parity_pcb_pairs.py::test_pcb_differential_pair_rule_coverage_parity",
    ),
)
