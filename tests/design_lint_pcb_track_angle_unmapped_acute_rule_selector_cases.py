"""Focused pytest nodes for unmapped acute-corner review."""

from __future__ import annotations

PCB_TRACK_ANGLE_UNMAPPED_ACUTE_RULE_NODE_CASES = (
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_unmapped_acute_corner_is_source_bound_and_names_track_geometry",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_threshold_is_exclusive_and_uses_millidegree_measurement",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_authored_angle_map_suppresses_unmapped_scope_prompt",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_arc_and_nonreciprocal_contacts_are_not_measured",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_review_is_opt_in_and_missing_or_unsupported_evidence_is_incomplete",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_rule_override_can_be_promoted_or_disabled_per_project",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_acute_corner_override_requires_a_pcb_project",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_unmapped_acute.py::test_metamorphic_translation_and_snapshot_order_preserve_angle",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_geometry_mcp_parity.py::test_unmapped_acute_corner_finding_matches_cli_and_mcp",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_design_lint_architecture_pcb_track_angle_unmapped_acute.py::test_rule_owner_is_the_pcb_geometry_predicate_and_is_reached_by_scan",
    ),
    (
        "pcb.unmapped_acute_track_corner_review",
        "tests/test_pcb_track_angle_geometry_native_fixture_lane.py::test_native_acute_corner_is_found_without_explicit_angle_rule",
    ),
)
