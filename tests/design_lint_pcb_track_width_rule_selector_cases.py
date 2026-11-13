"""Focused pytest nodes for native track-width scope coverage."""

from __future__ import annotations

PCB_TRACK_WIDTH_RULE_NODE_CASES = (
    (
        "pcb.track_width_unmapped_native_rule",
        "tests/test_pcb_track_width_unmapped_rules.py::test_unmapped_exact_native_track_width_scope_is_reviewed",
    ),
    (
        "pcb.track_width_unmapped_native_rule",
        "tests/test_pcb_track_width_unmapped_rules.py::test_mapped_exact_net_and_board_wide_scopes_are_quiet",
    ),
    (
        "pcb.track_width_unmapped_native_rule",
        "tests/test_pcb_track_width_unmapped_rules.py::test_nonliteral_scope_is_skipped",
    ),
    (
        "pcb.track_width_unmapped_native_rule",
        "tests/test_pcb_track_width_unmapped_rules.py::test_rule_order_does_not_change_unmapped_findings",
    ),
    (
        "pcb.track_width_unmapped_native_rule",
        "tests/test_design_lint_mcp_parity_pcb_track_width_unmapped.py::test_unmapped_track_width_scope_matches_between_cli_and_mcp",
    ),
)
