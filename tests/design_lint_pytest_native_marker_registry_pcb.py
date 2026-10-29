"""Expected markers for focused pcb lint suites."""

from types import MappingProxyType

PYTEST_NATIVE_LINT_SUITES = MappingProxyType(
    {
        "test_electrical_test_access_evidence.py": frozenset({"evidence_lint", "pcb_lint"}),
        "test_pcb_reference_plane_native_fixture_lane.py": frozenset(
            {"pcb_lint", "return_path_lint"}
        ),
        "test_pcb_switching_loop_native_fixture_lane.py": frozenset(
            {"pcb_lint", "return_path_lint"}
        ),
        "test_pcb_switching_loop_geometry.py": frozenset({"pcb_lint", "return_path_lint"}),
        "test_pcb_switching_loop_routes.py": frozenset({"pcb_lint", "return_path_lint"}),
        "test_pcb_return_path_native_fixture_lane.py": frozenset({"pcb_lint", "return_path_lint"}),
        "test_pcb_access_fixture_lane.py": frozenset({"pcb_lint"}),
        "test_pcb_touch_pad_clearance.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_touch_pad_clearance.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_required_fitted_reference.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_board_only.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_dnp.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_value.py": frozenset({"pcb_lint"}),
        "test_design_lint_determinism_pcb_pad_net.py": frozenset({"pcb_lint"}),
        "test_pcb_touch_pad_clearance_native.py": frozenset({"pcb_lint"}),
        "test_ci_hosted_pcb_fixture_schedule.py": frozenset({"pcb_lint", "return_path_lint"}),
    }
)
