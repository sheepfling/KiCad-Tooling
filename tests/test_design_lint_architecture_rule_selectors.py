"""Keep representative lint selectors focused on their catalogued cases."""

from __future__ import annotations

import pytest

from tests.design_lint_connector_rule_selector_cases import CONNECTOR_RULE_NODE_CASES
from tests.design_lint_numbered_return_selector_cases import NUMBERED_RETURN_RULE_NODE_CASES
from tests.design_lint_pcb_rule_selector_cases import PCB_RULE_NODE_CASES
from tests.design_lint_pcb_signal_path_unmapped_rule_selector_cases import (
    PCB_SIGNAL_PATH_UNMAPPED_RULE_NODE_CASES,
)
from tests.design_lint_power_supply_range_selector_cases import POWER_SUPPLY_RANGE_RULE_NODE_CASES
from tests.design_lint_rule_selector_cases import RULE_NODE_CASES as NON_PCB_RULE_NODE_CASES
from tests.design_lint_rule_selector_support import collect_rule_nodes

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]
RULE_NODE_CASES = (
    *NON_PCB_RULE_NODE_CASES,
    *NUMBERED_RETURN_RULE_NODE_CASES,
    *PCB_RULE_NODE_CASES,
    *PCB_SIGNAL_PATH_UNMAPPED_RULE_NODE_CASES,
    *CONNECTOR_RULE_NODE_CASES,
    *POWER_SUPPLY_RANGE_RULE_NODE_CASES,
)


def test_rule_markers_select_catalogued_cases_without_external_checkout() -> None:
    result = collect_rule_nodes(tuple(sorted({rule_id for rule_id, _ in RULE_NODE_CASES})))
    assert result.returncode == 0, result.stdout + result.stderr
    for _, expected_node in RULE_NODE_CASES:
        assert expected_node in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout


@pytest.mark.parametrize(
    ("rule_id", "selected_node"),
    (
        (
            "component.peer_power_output_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_power_output_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_signal_output_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_signal_output_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_signal_input_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_signal_input_unconnected_lint_cli_mcp_parity",
        ),
        (
            "component.peer_bidirectional_pin_unconnected",
            "tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_bidirectional_pin_unconnected_lint_cli_mcp_parity",
        ),
    ),
)
def test_peer_pin_rule_selector_collects_only_its_parity_case(
    rule_id: str,
    selected_node: str,
) -> None:
    result = collect_rule_nodes(rule_id)
    assert result.returncode == 0, result.stdout + result.stderr
    selected_peer_cases = {
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/test_design_lint_mcp_parity_peer_pins.py::test_peer_")
    }
    assert selected_peer_cases == {selected_node}


def test_rule_selector_filters_parametrized_peer_identity_cases() -> None:
    result = collect_rule_nodes("component.peer_signal_input_unconnected")
    assert result.returncode == 0, result.stdout + result.stderr
    selected_identity_cases = {
        line
        for line in result.stdout.splitlines()
        if line.startswith("tests/test_peer_component_pin_identity.py::")
    }
    assert selected_identity_cases == {
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_cover_each_typed_peer_rule[input-IN-component.peer_signal_input_unconnected]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_peer_pin_assignment_matches_between_cli_and_mcp[signal-input]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_accept_identical_generic_pin_metadata[input-component.peer_signal_input_unconnected]",
        "tests/test_peer_component_pin_identity.py::test_shared_part_id_aliases_skip_mismatched_pin_functions[input-IN-component.peer_signal_input_unconnected]",
    }


def test_alternate_reference_plane_selector_stays_with_its_fault_control_and_parity_cases() -> None:
    result = collect_rule_nodes("pcb.alternate_reference_plane_run")
    assert result.returncode == 0, result.stdout + result.stderr
    selected = {
        line
        for line in result.stdout.splitlines()
        if line.startswith(
            (
                "tests/test_pcb_alternate_reference_plane_run.py::",
                "tests/test_pcb_reference_plane_native_fixture_lane.py::",
                "tests/test_design_lint_mcp_parity_pcb_alternate_reference_plane.py::",
            )
        )
    }
    assert selected == {
        "tests/test_pcb_alternate_reference_plane_run.py::test_authored_alternate_net_threshold_emits_exact_review_candidate",
        "tests/test_pcb_alternate_reference_plane_run.py::test_disjoint_alternate_plane_intervals_are_localized_separately",
        "tests/test_pcb_alternate_reference_plane_run.py::test_legacy_coverage_reports_keep_aggregate_findings_without_coordinates",
        "tests/test_pcb_alternate_reference_plane_run.py::test_alternate_net_review_is_opt_in_and_threshold_boundary_is_exact",
        "tests/test_pcb_alternate_reference_plane_run.py::test_alternate_plane_evidence_is_stable_under_zone_order_and_policy_can_disable",
        "tests/test_pcb_reference_plane_native_fixture_lane.py::test_native_alternate_reference_net_fault_control_repeats[controller-10.0.0]",
        "tests/test_pcb_reference_plane_native_fixture_lane.py::test_native_alternate_reference_net_fault_control_repeats[raspberry-pi-status-led-10.0.5]",
        "tests/test_design_lint_mcp_parity_pcb_alternate_reference_plane.py::test_alternate_reference_plane_rule_matches_cli_and_mcp",
    }


def test_serial_reference_rule_selects_its_exact_native_regressions() -> None:
    rule_id = "bus.serial_peer_reference_review"
    result = collect_rule_nodes(rule_id)
    assert result.returncode == 0, result.stdout + result.stderr
    for function in (
        "test_serial_peer_voltage_fault_and_controls_by_native_version",
        "test_serial_connector_and_optical_isolation_boundaries_by_native_version",
        "test_serial_label_alias_fault_and_control_by_native_version",
        "test_serial_peer_normalized_netlists_match_across_native_versions",
    ):
        assert f"tests/test_ci_hosted_digital_peer_serial.py::{function}" in result.stdout
    assert "tests/test_power_paths.py::" not in result.stdout
