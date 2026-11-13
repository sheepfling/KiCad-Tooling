"""Focused pytest nodes for the per-net track-angle coverage gate."""

from __future__ import annotations

PCB_TRACK_ANGLE_RULE_NODE_CASES = (
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_native_parser_marks_unsupported_angle_bounds",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_missing_mismatched_or_suppressed_coverage_is_reported",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_duplicate_or_overriding_rules_are_not_credited",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_candidate_is_review_mode_and_policy_off_skips_source_reads",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_exact_project_requirement_is_covered_by_the_saved_rule",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_native_parser_reads_unitless_integer_angle_bounds",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_native_parser_rejects_repeated_or_reversed_angle_bounds",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_exact_net_condition_disjointness_proves_only_literal_inequality",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_rule_coverage.py::test_map_requires_reviewable_unique_exact_net_scopes",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_design_lint_mcp_parity_pcb_track_angle.py::test_track_angle_coverage_finding_matches_cli_and_mcp",
    ),
    (
        "pcb.track_angle_rule_coverage",
        "tests/test_pcb_track_angle_native_fixture_lane.py::test_native_track_angle_fault_is_reported_and_collinear_control_is_clean",
    ),
)
