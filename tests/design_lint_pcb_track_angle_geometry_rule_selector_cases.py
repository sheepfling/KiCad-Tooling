"""Focused pytest nodes for the opt-in track-angle geometry rule gate."""

from __future__ import annotations

from tests.design_lint_pcb_track_angle_unmapped_acute_rule_selector_cases import (
    PCB_TRACK_ANGLE_UNMAPPED_ACUTE_RULE_NODE_CASES,
)

PCB_TRACK_ANGLE_GEOMETRY_RULE_NODE_CASES = (
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_authored_minimum_detects_135_degree_corner_and_accepts_collinear_control",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_integer_geometry_measurement_is_stable_at_authored_boundaries",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_metamorphic_translation_rotation_and_snapshot_order_preserve_angle",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_maximum_bound_flags_straight_continuation",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_arc_contacts_are_skipped",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_branch_pad_and_via_vertices_are_skipped",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_nonreciprocal_native_contacts_are_skipped",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_candidate_carries_board_map_probe_and_track_identity",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_unsupported_kicad_version_stays_incomplete",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_capture_failure_and_missing_map_are_explicit_candidates",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry.py::test_geometry_review_is_opt_in_and_requires_authored_scope",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry_mcp_parity.py::test_mapped_track_angle_finding_matches_cli_and_mcp",
    ),
    (
        "pcb.track_angle_geometry_review",
        "tests/test_pcb_track_angle_geometry_native_fixture_lane.py::test_native_snapshot_angle_matches_synthetic_fault_and_control",
    ),
    *PCB_TRACK_ANGLE_UNMAPPED_ACUTE_RULE_NODE_CASES,
)
