"""Focused pytest nodes for unmatched exact-netclass custom DRC scopes."""

from __future__ import annotations

PCB_EXACT_NETCLASS_SCOPE_RULE_NODE_CASES = (
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope.py::test_absent_exact_class_selector_is_reviewed_with_bound_sources",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope.py::test_project_class_sources_and_casefold_controls_are_quiet",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope.py::test_casefold_equivalent_absent_selectors_group_deterministically",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope.py::test_unsupported_shapes_and_ambiguous_project_inventories_stay_quiet",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope.py::test_disabled_or_unmeasured_scans_do_not_read_native_sources",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_design_lint_mcp_parity_pcb_drc_exact_netclass_scope.py::test_unmatched_exact_netclass_scope_matches_between_cli_and_mcp",
    ),
    (
        "pcb.drc_exact_netclass_scope_unmatched",
        "tests/test_pcb_drc_exact_netclass_scope_native.py::test_exact_netclass_selector_behavior_and_project_references_are_deterministic",
    ),
)
